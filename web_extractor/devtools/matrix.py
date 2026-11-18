"""Ejecuta la matriz de pruebas contra los fixtures locales y escribe evidencias reproducibles.

Todas las ejecuciones usan el **mismo motor** con configuraciones distintas (``examples/*.yaml``).
El resultado observado se toma de la ejecución real en esta máquina; nada se rellena a mano.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from web_extractor.config.loader import load_config, parse_config
from web_extractor.config.templates import default_config_dict
from web_extractor.config.schema import ProjectConfig
from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.errors import AuthorizationError, ConfigError
from web_extractor.core.limits import CancelToken
from web_extractor.devtools.fixture_server import DEFAULT_API_TOKEN, DEFAULT_PASSWORD, DEFAULT_USER, FixtureServer
from web_extractor.selection.suggest import suggest_extraction
from web_extractor.utils.timeutils import utc_now_iso

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@dataclass
class MatrixRow:
    id: str
    scenario: str
    method: str
    environment: str
    fields: str
    request_limit: str
    expected: str
    observed: str = ""
    evidence: str = ""
    errors: str = ""
    decision: str = ""
    passed: bool = False
    server_hits: int = 0
    extra: dict = field(default_factory=dict)


def _with_output(cfg: ProjectConfig, directory: Path, **extraction_updates) -> ProjectConfig:
    output = cfg.output.model_copy(update={"directory": str(directory)})
    update: dict = {"output": output}
    if extraction_updates:
        update["extraction"] = cfg.extraction.model_copy(update=extraction_updates)
    return cfg.model_copy(update=update)


def _row_from_run(row: MatrixRow, result, expected_status: set[str], check: Callable | None = None) -> MatrixRow:
    q, b = result.quality, result.budget
    row.observed = (f"estado={result.status}; registros={q.exported} (crudos {q.total_raw}, válidos {q.valid}, "
                    f"advert. {q.with_warnings}, inválidos {q.invalid}, dup. {q.duplicates_removed}); "
                    f"solicitudes={b.get('requests')}/{b.get('max_requests')}; páginas={b.get('pages')}; "
                    f"clics={b.get('clicks')}; scrolls={b.get('scrolls')}")
    row.evidence = result.outputs.get("report", "")
    row.errors = "; ".join(f"{i.kind}: {i.message}" for i in result.incidents)[:300] or "—"
    stopped = result.status in ("detenido_barrera", "parcial_barrera", "detenido_politica", "cancelado", "fallido")
    row.decision = "Detenerse" if stopped or result.requires_human_review else "Continuar"
    if result.requires_human_review:
        row.decision += " (revisión humana)"
    ok = result.status in expected_status
    if ok and check is not None:
        ok = bool(check(result))
    row.passed = ok
    return row


def run_matrix(output_dir: Path, include_browser: bool = True, docs_path: Path | None = None) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("WE_FIXTURE_USER", DEFAULT_USER)
    os.environ.setdefault("WE_FIXTURE_PASSWORD", DEFAULT_PASSWORD)
    os.environ.setdefault("WE_FIXTURE_API_TOKEN", DEFAULT_API_TOKEN)
    rows: list[MatrixRow] = []
    with FixtureServer() as server:
        os.environ["FIXTURE_BASE_URL"] = server.base_url

        def run_case(row: MatrixRow, cfg: ProjectConfig, expected: set[str], check=None, cancel_after: float | None = None):
            before = len(server.hits)
            cancel = CancelToken()
            engine = ExtractionEngine(cfg, cancel=cancel)
            diagnosis = None
            if cfg.extraction.method != "browser" or include_browser:
                diagnosis = engine.diagnose(render=False)
            timer = threading.Timer(cancel_after, cancel.cancel, args=("cancelación de prueba",)) if cancel_after else None
            if timer:
                timer.start()
            try:
                result = engine.run(confirmed=True)
            finally:
                if timer:
                    timer.cancel()
            _row_from_run(row, result, expected, check)
            row.server_hits = len(server.hits) - before
            if diagnosis is not None and diagnosis.best:
                row.extra["diagnóstico"] = f"{diagnosis.best.method} ({diagnosis.best.confidence}, {diagnosis.best.score})"
            elif diagnosis is not None and diagnosis.stopped:
                row.extra["diagnóstico"] = "detenido: " + ", ".join(i.kind for i in diagnosis.incidents)
            rows.append(row)
            return result

        def case(id_, file, scenario, expected_text, expected_status, check=None, **kw):
            cfg = _with_output(load_config(EXAMPLES / file), output_dir)
            row = MatrixRow(id_, scenario, cfg.extraction.method, cfg.authorization.environment,
                            ", ".join(f.name for f in cfg.extraction.fields), str(cfg.limits.max_requests), expected_text)
            return run_case(row, cfg, expected_status, check, **kw)

        case("T01", "f01_catalogo_estatico.yaml", "HTML estático + paginación por enlace",
             "3 páginas, 10 registros exportados (1 duplicado eliminado, 1 inválido sin SKU)", {"completado"},
             lambda r: r.budget["pages"] == 3 and r.quality.exported == 10 and r.quality.duplicates_removed == 1)
        case("T02", "f02_tabla_html.yaml", "Tabla HTML", "5 filas tras deduplicar, advertencias por N/D y cifra pendiente",
             {"completado"}, lambda r: r.quality.exported == 5 and r.quality.with_warnings == 2)
        if include_browser:
            case("T03", "f03_js_renderizado.yaml", "Contenido renderizado con JavaScript (Selenium)",
                 "5 novedades obtenidas del DOM renderizado", {"completado"}, lambda r: r.quality.exported == 5)
            case("T04", "f04_cargar_mas.yaml", "Botón «Cargar más» con max_clicks=2",
                 "12 de 14 eventos; parada por max_clicks", {"completado_con_limites"},
                 lambda r: r.quality.exported == 12 and r.budget["clicks"] == 2)
            case("T05", "f05_scroll_infinito.yaml", "Scroll infinito con max_scrolls=2",
                 "15 de 20 obras; parada por max_scrolls", {"completado_con_limites"},
                 lambda r: r.quality.exported == 15 and r.budget["scrolls"] == 2)
        case("T06", "f06_api_documentada.yaml", "API pública documentada (JSON) + paginación links.next",
             "9 productos en 3 páginas", {"completado"}, lambda r: r.quality.exported == 9 and r.budget["pages"] == 3)
        case("T07", "f07_archivo_csv.yaml", "Archivo estructurado CSV descargable",
             "5 estaciones tras deduplicar; latitud y fecha inválidas como advertencia", {"completado"},
             lambda r: r.quality.exported == 5 and r.quality.duplicates_removed == 1)
        case("T08", "f08_autenticacion_autorizada.yaml", "Autenticación autorizada (credenciales ficticias por variables de entorno)",
             "5 informes tras iniciar sesión; contraseña ausente de logs", {"completado"},
             lambda r: r.quality.exported == 5 and DEFAULT_PASSWORD not in Path(r.outputs["log"]).read_text(encoding="utf-8"))
        case("T09", "f09_barrera_captcha.yaml", "CAPTCHA", "Parada segura con incidencia 'captcha', sin reintentos",
             {"detenido_barrera"}, lambda r: any(i.kind == "captcha" for i in r.incidents))
        case("T10", "f10_limite_tasa.yaml", "Límite de tasa (HTTP 429)", "Parada segura 'rate_limit', 1 sola solicitud a la ruta",
             {"detenido_barrera"}, lambda r: any(i.kind == "rate_limit" for i in r.incidents))
        before = len(server.hits)
        case("T11", "f11_robots_prohibido.yaml", "Ruta prohibida por robots.txt",
             "Detenido por política; la ruta /privado/ nunca se solicita", {"detenido_politica"},
             lambda r: not any("/privado/" in h for h in server.hits[before:]))

        cfg = _with_output(load_config(EXAMPLES / "f01_catalogo_estatico.yaml"), output_dir)
        cfg = cfg.model_copy(update={"limits": cfg.limits.model_copy(update={"delay_seconds": 1.0}),
                                     "project": cfg.project.model_copy(update={"name": "t12-cancelacion"})})
        row = MatrixRow("T12", "Cancelación durante la paginación", "static_html", "fixture", "(F01)",
                        str(cfg.limits.max_requests), "Estado 'cancelado' antes de recorrer las 3 páginas")
        run_case(row, cfg, {"cancelado"}, lambda r: r.budget["pages"] < 3, cancel_after=1.5)

        cfg = _with_output(load_config(EXAMPLES / "f01_catalogo_estatico.yaml"), output_dir)
        fields = [f.model_copy(update={"selector": ".precio-rediseñado"}) if f.name == "precio" else f
                  for f in cfg.extraction.fields]
        cfg = _with_output(cfg, output_dir, fields=fields)
        row = MatrixRow("T13", "Detección de cambios: selector de precio roto frente al perfil de T01", "static_html",
                        "fixture", "(F01)", str(cfg.limits.max_requests),
                        "Cambio de severidad alta, revisión humana, perfil no actualizado")
        run_case(row, cfg, {"completado"}, lambda r: r.requires_human_review)

        rows.extend(_unseen_site_cases(server, output_dir))

    rows.extend(_config_cases())
    return _write(rows, output_dir, docs_path)


def _unseen_site_cases(server: FixtureServer, output_dir: Path) -> list[MatrixRow]:
    """Sitio sin YAML de ejemplo: solo plantilla desde la URL + reglas sugeridas por el diagnóstico."""
    rows = []
    data = default_config_dict(f"{server.base_url}/nuevo/agenda", "t17-sitio-no-visto")
    data["output"]["directory"] = str(output_dir)
    before = len(server.hits)
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    suggestion = suggest_extraction(diagnosis) or {}
    row = MatrixRow("T17", "Sitio no visto (sin YAML de ejemplo, ISO-8859-1): reglas 100 % sugeridas",
                    suggestion.get("method", "—"), "fixture", ", ".join(f["name"] for f in suggestion.get("fields", [])),
                    str(data["limits"]["max_requests"]),
                    "Diagnóstico → sugerencia → extracción sin editar reglas; 7 eventos con acentos correctos; "
                    "parada por max_pages=2")
    row.extra["diagnóstico"] = (f"{diagnosis.best.method} ({diagnosis.best.confidence}, {diagnosis.best.score})"
                                if diagnosis.best else "sin recomendación")
    data["extraction"] = suggestion
    data["authorization"].update(confirmed=True, authorized_by="Equipo docente (fixture local)",
                                 purpose="Validar el flujo genérico", terms_reviewed=True)
    result = ExtractionEngine(parse_config(data)).run(confirmed=True)
    _row_from_run(row, result, {"completado_con_limites"},
                  lambda r: r.quality.exported == 7 and any(x.data.get("lugar") == "Biblioteca Ñuñoa" for x in r.records))
    row.server_hits = len(server.hits) - before
    rows.append(row)

    data = default_config_dict(f"{server.base_url}/nuevo/redirige", "t18-redireccion")
    before = len(server.hits)
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    row = MatrixRow("T18", "Sitio no visto que redirige a otro host (127.0.0.1 → localhost)", "auto", "fixture", "—",
                    str(data["diagnosis"]["max_requests"]), "Redirección no seguida; incidencia out_of_scope con paso legítimo")
    row.observed = f"detenido={diagnosis.stopped}; solicitudes={diagnosis.requests_used}"
    row.errors = "; ".join(f"{i.kind}: {i.message}" for i in diagnosis.incidents)[:300] or "—"
    row.decision = "Detenerse"
    row.server_hits = len(server.hits) - before
    row.passed = (diagnosis.stopped and any(i.kind == "out_of_scope" for i in diagnosis.incidents)
                  and not any("/nuevo/agenda" in h for h in server.hits[before:]))
    row.extra["diagnóstico"] = "detenido: " + ", ".join(i.kind for i in diagnosis.incidents)
    rows.append(row)
    return rows


def _config_cases() -> list[MatrixRow]:
    rows = []
    row = MatrixRow("T14", "Configuración inválida (ftp, secreto, campo sensible, tipos desconocidos)", "—", "—", "—", "—",
                    "Rechazo con mensajes por campo, sin solicitudes")
    try:
        load_config(EXAMPLES / "invalida_ejemplo.yaml")
        row.observed = "aceptada (inesperado)"
    except ConfigError as exc:
        row.observed = f"rechazada con {len(exc.messages)} errores: " + " | ".join(exc.messages)[:300]
        row.passed = True
    row.decision = "Detenerse"
    rows.append(row)

    row = MatrixRow("T15", "Sitio real sin autorización confirmada (plantilla)", "auto", "production", "titulo", "5",
                    "Extracción bloqueada; se enumera lo que falta")
    try:
        cfg = load_config(EXAMPLES / "plantilla_sitio_autorizado.yaml")
        ExtractionEngine(cfg).run(confirmed=True)
        row.observed = "ejecutada (inesperado)"
    except AuthorizationError as exc:
        row.observed = f"bloqueada; faltan {len(exc.missing)} requisitos: " + " | ".join(exc.missing)[:300]
        row.passed = True
    row.decision = "Detenerse"
    rows.append(row)

    row = MatrixRow("T16", "API sin documentación verificada", "api", "fixture", "(F06)", "8",
                    "Marcada 'no verificado / no ejecutar'; sin solicitudes")
    cfg = load_config(EXAMPLES / "f06_api_documentada.yaml")
    cfg = cfg.model_copy(update={"extraction": cfg.extraction.model_copy(
        update={"api": cfg.extraction.api.model_copy(update={"documented": False, "documentation_url": None})})})
    try:
        ExtractionEngine(cfg).run(confirmed=True)
        row.observed = "ejecutada (inesperado)"
    except AuthorizationError as exc:
        row.observed = "bloqueada: " + " | ".join(exc.missing)
        row.passed = True
    row.decision = "Detenerse"
    rows.append(row)
    return rows


def _write(rows: list[MatrixRow], output_dir: Path, docs_path: Path | None) -> int:
    payload = {"generated_at": utc_now_iso(), "rows": [asdict(r) for r in rows]}
    (output_dir / "matriz_resultados.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Matriz de pruebas — resultados observados",
        "",
        f"Generado automáticamente el {payload['generated_at']} (UTC) con `python -m web_extractor matrix` contra los "
        "fixtures locales. Ningún sitio público fue consultado.",
        "",
        "| ID | Escenario | Método | Entorno | Campos | Límite sol. | Esperado | Observado | Diagnóstico | Incidencias | Decisión | Solicitudes al servidor | ¿Cumple? |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cells = [r.id, r.scenario, r.method, r.environment, r.fields, r.request_limit, r.expected, r.observed,
                 r.extra.get("diagnóstico", "—"), r.errors or "—", r.decision, str(r.server_hits), "sí" if r.passed else "NO"]
        lines.append("| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |")
    lines += ["", "Evidencias por ejecución (informe, CSV, JSON, log y acciones):", ""]
    lines += [f"- {r.id}: `{r.evidence}`" for r in rows if r.evidence]
    text = "\n".join(lines) + "\n"
    (output_dir / "matriz_resultados.md").write_text(text, encoding="utf-8")
    if docs_path:
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        docs_path.write_text(text, encoding="utf-8")
    passed = sum(r.passed for r in rows)
    print(f"Matriz: {passed}/{len(rows)} casos cumplen lo esperado. Resultados en {output_dir / 'matriz_resultados.md'}")
    return 0 if passed == len(rows) else 1
