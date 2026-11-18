"""CLI con pasos guiados (interfaz mínima viable). Uso: ``python -m web_extractor <comando>``.

Códigos de salida: 0 ok · 1 error técnico · 2 configuración inválida · 3 falta autorización o
confirmación · 4 parada por barrera/política · 5 cancelado · 6 requiere revisión humana.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from web_extractor import __version__
from web_extractor.config.loader import load_config, parse_config
from web_extractor.config.schema import ProjectConfig
from web_extractor.config.templates import default_config_dict
from web_extractor.core.authorization import missing_for_diagnosis, missing_for_extraction
from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.errors import AuthorizationError, ConfigError
from web_extractor.core.limits import CancelToken
from web_extractor.interface import console
from web_extractor.reports.diagnosis_report import write_diagnosis
from web_extractor.reports.profiles import compare_profiles
from web_extractor.selection.suggest import suggest_extraction
from web_extractor.utils.logging_utils import setup_logging
from web_extractor.utils.timeutils import utc_now

EXIT_OK, EXIT_ERROR, EXIT_CONFIG, EXIT_AUTH, EXIT_STOPPED, EXIT_CANCELLED, EXIT_REVIEW = range(7)
STATUS_EXIT = {"completado": EXIT_OK, "completado_con_limites": EXIT_OK, "parcial_barrera": EXIT_STOPPED,
               "detenido_barrera": EXIT_STOPPED, "detenido_politica": EXIT_STOPPED, "cancelado": EXIT_CANCELLED,
               "fallido": EXIT_ERROR}


def _install_cancel_handler(cancel: CancelToken) -> None:
    def handler(signum, frame):  # noqa: ARG001
        if cancel.cancelled:
            raise KeyboardInterrupt
        console.out("\nCancelación solicitada: se detendrá tras la acción en curso (Ctrl+C otra vez para abortar).")
        cancel.cancel("Ctrl+C del usuario")

    signal.signal(signal.SIGINT, handler)


def _engine(cfg: ProjectConfig) -> ExtractionEngine:
    cancel = CancelToken(Path(cfg.output.directory) / cfg.output.stop_file)
    _install_cancel_handler(cancel)
    return ExtractionEngine(cfg, cancel=cancel)


def _confirm_diagnosis(cfg: ProjectConfig, assume_yes: bool) -> bool:
    if cfg.authorization.environment == "fixture" or assume_yes:
        return True
    return console.ask_yes_no(
        f"El diagnóstico hará hasta {cfg.diagnosis.max_requests} solicitud(es) a {urlsplit(cfg.target_url).netloc}. "
        "¿Confirma que tiene permiso para esta inspección?")


def cmd_validate(args) -> int:
    cfg = load_config(args.config)
    console.out(f"Configuración válida: {args.config} (proyecto '{cfg.project.name}', método {cfg.extraction.method})")
    missing = missing_for_extraction(cfg)
    console.show_authorization(cfg, missing)
    if not missing:
        console.out("\nAutorización declarada completa: se puede previsualizar y extraer tras confirmar.")
    return EXIT_OK


def _diagnose(cfg: ProjectConfig, engine: ExtractionEngine, render: bool | None, assume_yes: bool):
    missing = missing_for_diagnosis(cfg)
    if missing:
        raise AuthorizationError(missing)
    if not _confirm_diagnosis(cfg, assume_yes):
        console.out("Diagnóstico no confirmado; no se realizó ninguna solicitud.")
        return None
    diagnosis = engine.diagnose(render=render)
    console.show_diagnosis(diagnosis)
    stem = f"diagnostico_{utc_now().strftime('%Y%m%dT%H%M%SZ')}"
    paths = write_diagnosis(diagnosis, Path(cfg.output.directory) / cfg.project.name, stem)
    console.out(f"\nInforme de diagnóstico: {paths['markdown']}")
    return diagnosis


def cmd_diagnose(args) -> int:
    cfg = load_config(args.config)
    diagnosis = _diagnose(cfg, _engine(cfg), True if args.render else None, args.yes)
    if diagnosis is None:
        return EXIT_AUTH
    return EXIT_STOPPED if diagnosis.stopped else EXIT_OK


def cmd_suggest(args) -> int:
    cfg = load_config(args.config)
    diagnosis = _diagnose(cfg, _engine(cfg), True if args.render else None, args.yes)
    if diagnosis is None or diagnosis.stopped:
        return EXIT_STOPPED
    suggestion = suggest_extraction(diagnosis)
    if suggestion is None:
        console.out("\nNo hay candidatos fiables: defina las reglas manualmente (modo manual) y use 'preview'.")
        return EXIT_OK
    console.heading("Borrador de reglas sugeridas (revíselas antes de usarlas)")
    console.out(yaml.safe_dump({"extraction": suggestion}, allow_unicode=True, sort_keys=False))
    if args.out:
        data = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
        data["extraction"] = suggestion
        Path(args.out).write_text("# BORRADOR generado por 'suggest': revise selectores, tipos y reglas.\n"
                                  + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        console.out(f"Borrador guardado en {args.out}")
    return EXIT_OK


def cmd_preview(args) -> int:
    cfg = load_config(args.config)
    engine = _engine(cfg)
    if not args.from_file:
        missing = missing_for_extraction(cfg)
        if missing:
            console.show_authorization(cfg, missing)
            console.out("\nUse --from-file con un HTML/JSON/CSV guardado localmente para probar reglas sin solicitudes.")
            return EXIT_AUTH
        if cfg.authorization.environment != "fixture" and not args.yes and not console.ask_yes_no(
                "La vista previa hará hasta 2 solicitudes (1 página). ¿Continuar?"):
            return EXIT_AUTH
    preview = engine.preview(max_records=args.n, from_file=Path(args.from_file) if args.from_file else None)
    console.show_preview(preview)
    return EXIT_STOPPED if preview.incidents else EXIT_OK


def cmd_run(args) -> int:
    cfg = load_config(args.config)
    engine = _engine(cfg)
    console.out(f"web_extractor {__version__} — flujo guiado para '{cfg.project.name}'")
    missing = missing_for_extraction(cfg)
    console.show_authorization(cfg, missing)
    if missing:
        console.out("\nNo se realizará extracción. Complete la autorización o limite el trabajo a diagnóstico/fixtures.")
        return EXIT_AUTH

    if not args.skip_diagnosis:
        diagnosis = _diagnose(cfg, engine, None, args.yes)
        if diagnosis is None:
            return EXIT_AUTH
        if diagnosis.stopped:
            console.out("\nEl diagnóstico se detuvo por una barrera o política; no se continúa con la extracción.")
            return EXIT_STOPPED
        best = diagnosis.best
        if best and best.method != cfg.extraction.method:
            console.out(f"\nAviso: el diagnóstico sugiere '{best.method}' ({best.confidence}) y la configuración usa "
                        f"'{cfg.extraction.method}'. Se respeta la elección del usuario.")

    if not args.skip_preview:
        preview = engine.preview(max_records=5)
        console.show_preview(preview)
        if preview.incidents:
            console.out("\nLa vista previa encontró una barrera o error; no se continúa.")
            return EXIT_STOPPED

    lim = cfg.limits
    question = (f"\n¿Iniciar la extracción de {cfg.target_url} con un máximo de {lim.max_requests} solicitudes, "
                f"{lim.max_pages} páginas y {lim.max_records} registros?")
    confirmed = args.yes or console.ask_yes_no(question)
    if not confirmed:
        console.out("Extracción no confirmada. No se hicieron solicitudes de extracción.")
        return EXIT_AUTH
    if args.yes:
        console.out(f"{question} -> confirmado con --yes")
    result = engine.run(confirmed=True)
    console.show_run(result)
    if result.requires_human_review:
        return EXIT_REVIEW
    return STATUS_EXIT.get(result.status, EXIT_ERROR)


def _load_profile(path: str) -> dict:
    p = Path(path)
    if p.is_dir():
        p = p / "profile.json"
    return json.loads(p.read_text(encoding="utf-8"))


def cmd_compare(args) -> int:
    changes = compare_profiles(_load_profile(args.previous), _load_profile(args.current))
    if not changes:
        console.out("Sin cambios relevantes entre las ejecuciones.")
        return EXIT_OK
    for change in changes:
        console.out(f"[{change['severity']}] {change['kind']}: {change['message']}")
    return EXIT_REVIEW if any(c["severity"] == "alta" for c in changes) else EXIT_OK


def cmd_init(args) -> int:
    url = args.url
    interactive = not args.non_interactive and sys.stdin.isatty()
    data = default_config_dict(url, args.name)
    data["project"]["description"] = "Describa el conjunto de datos autorizado"
    if interactive:
        console.heading("Asistente de configuración")
        auth = data["authorization"]
        auth["authorized_by"] = console.ask("¿Quién autoriza el acceso? (nombre/organización, vacío si nadie)") or None
        auth["purpose"] = console.ask("¿Finalidad del uso de los datos?") or None
        auth["terms_reviewed"] = console.ask_yes_no("¿Revisó términos de uso, licencia y políticas del sitio?")
        auth["evidence_reference"] = console.ask("Referencia del permiso (correo, contrato, ticket)") or None
        auth["confirmed"] = bool(auth["authorized_by"] and auth["purpose"] and auth["terms_reviewed"]
                                 and console.ask_yes_no("¿Confirma que tiene autorización para este alcance?"))
        prefix = console.ask("Prefijo de ruta autorizado", urlsplit(url).path or "/")
        data["scope"]["allowed_path_prefixes"] = [prefix if prefix.startswith("/") else "/" + prefix]
    try:
        parse_config(data)
    except ConfigError as exc:
        console.out(str(exc))
        return EXIT_CONFIG
    out_path = Path(args.out)
    out_path.write_text("# Generado por 'init'. Complete autorización y reglas tras el diagnóstico.\n"
                        + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    console.out(f"Configuración creada en {out_path}. Siguiente paso: python -m web_extractor diagnose {out_path}")
    return EXIT_OK


def cmd_serve(args) -> int:
    from web_extractor.devtools.fixture_server import FixtureServer

    server = FixtureServer(args.host, args.port).start()
    console.out(f"Fixtures locales en {server.base_url} (Ctrl+C para detener). Datos 100 % ficticios.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
    return EXIT_OK


def cmd_gui(args) -> int:
    import subprocess

    root = Path(__file__).resolve().parent.parent
    script = root / "web_extractor" / "gui" / "app.py"
    command = [sys.executable, "-m", "streamlit", "run", str(script), "--server.address", args.host,
               "--server.port", str(args.port), "--server.headless", str(args.headless).lower(),
               "--browser.gatherUsageStats", "false"]
    console.out(f"Interfaz gráfica en http://{args.host}:{args.port} (Ctrl+C para detener)")
    try:
        return subprocess.call(command, cwd=root)
    except KeyboardInterrupt:
        return EXIT_OK


def cmd_matrix(args) -> int:
    from web_extractor.devtools.matrix import run_matrix

    return run_matrix(Path(args.output), include_browser=not args.skip_browser, docs_path=Path(args.docs) if args.docs else None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="web_extractor", description="Diagnóstico y extracción web responsable")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--log-level", default="WARNING", help="DEBUG, INFO, WARNING (por defecto)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="Valida la configuración y muestra el estado de autorización")
    p.add_argument("config")
    p.set_defaults(func=cmd_validate)

    for name, func, help_text in (("diagnose", cmd_diagnose, "Diagnóstico pasivo y método sugerido"),
                                  ("suggest", cmd_suggest, "Diagnóstico + borrador de reglas de campos")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("config")
        p.add_argument("--render", action="store_true", help="Comparar con render de Selenium (+1 solicitud)")
        p.add_argument("--yes", action="store_true", help="Confirmar sin preguntar")
        if name == "suggest":
            p.add_argument("--out", help="Guardar un borrador de configuración")
        p.set_defaults(func=func)

    p = sub.add_parser("preview", help="Vista previa de registros (1 página o archivo local)")
    p.add_argument("config")
    p.add_argument("--from-file", help="HTML/JSON/CSV local: prueba reglas sin solicitudes")
    p.add_argument("-n", type=int, default=5)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("run", help="Flujo guiado completo: diagnóstico, vista previa, confirmación, extracción")
    p.add_argument("config")
    p.add_argument("--yes", action="store_true", help="Confirmación explícita no interactiva")
    p.add_argument("--skip-diagnosis", action="store_true")
    p.add_argument("--skip-preview", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("compare-runs", help="Compara perfiles de dos ejecuciones (directorios o profile.json)")
    p.add_argument("previous")
    p.add_argument("current")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("init", help="Crea una configuración inicial para una URL")
    p.add_argument("--url", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--name")
    p.add_argument("--non-interactive", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("serve-fixtures", help="Sirve el sitio de pruebas local")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("matrix", help="Ejecuta la matriz de pruebas contra los fixtures y guarda evidencias")
    p.add_argument("--output", default="outputs/matrix")
    p.add_argument("--docs", default="docs/evidencias/matriz_resultados.md")
    p.add_argument("--skip-browser", action="store_true")
    p.set_defaults(func=cmd_matrix)

    p = sub.add_parser("gui", help="Abre la interfaz gráfica local (Streamlit)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8611)
    p.add_argument("--headless", action="store_true", help="No abrir el navegador automáticamente")
    p.set_defaults(func=cmd_gui)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)
    try:
        return args.func(args)
    except ConfigError as exc:
        console.out(str(exc))
        return EXIT_CONFIG
    except AuthorizationError as exc:
        console.out(str(exc))
        return EXIT_AUTH
    except KeyboardInterrupt:
        console.out("Abortado.")
        return EXIT_CANCELLED


if __name__ == "__main__":
    raise SystemExit(main())
