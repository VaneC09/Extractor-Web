"""Interfaz gráfica local del extractor (Streamlit).

Ejecutar con ``python -m web_extractor gui``. Una página guiada que sigue el flujo del reto:
URL → autorización → diagnóstico → datos a extraer y vista previa → configuración y ejecución →
resultados. Cada sección aparece cuando la anterior está lista. Todas las acciones que generan
solicitudes pasan por las mismas puertas de autorización del motor.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pandas as pd
import streamlit as st
import yaml

# `streamlit run` solo añade la carpeta del script a sys.path; el paquete vive dos niveles arriba.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from web_extractor.config.loader import parse_config
from web_extractor.config.schema import ProjectConfig
from web_extractor.config.templates import FIELD_COLUMNS, default_config_dict, fields_to_rows, rows_to_fields
from web_extractor.core.authorization import missing_for_diagnosis, missing_for_extraction
from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.errors import AuthorizationError, ConfigError, WebExtractorError
from web_extractor.gui.jobs import ExtractionJob
from web_extractor.reports.diagnosis_report import diagnosis_markdown
from web_extractor.reports.intervention import GENERAL_LOG, INTERVENTION_LOG, guide_for
from web_extractor.reports.run_report import STATUS_TEXT
from web_extractor.selection.suggest import suggest_extraction
from web_extractor.transforms.casting import SUPPORTED_TYPES
from web_extractor.transforms.normalizers import NORMALIZERS

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = Path(os.environ.get("WE_GUI_EXAMPLES_DIR") or ROOT / "examples" / "reales")

METHODS = {
    "auto": "Automático (solo diagnóstico)",
    "static_html": "HTML estático (Requests + BeautifulSoup)",
    "browser": "Navegador (Selenium)",
    "structured_file": "Archivo CSV/JSON/XML descargable",
    "api": "API pública documentada",
}
STATUS_STYLE = {
    "completado": "success", "completado_con_limites": "info", "parcial_barrera": "warning",
    "detenido_barrera": "error", "detenido_politica": "error", "cancelado": "warning", "fallido": "error",
}

# Widgets simples: clave de sesión -> ruta en el diccionario de configuración.
SIMPLE_WIDGETS = [
    "project.name", "project.description", "target_url", "user_agent",
    "authorization.environment", "authorization.authorized_by", "authorization.purpose",
    "authorization.terms_reviewed", "authorization.evidence_reference", "authorization.valid_until",
    "authorization.allow_authentication", "authorization.confirmed",
    "scope.allowed_schemes", "scope.allow_private_network", "scope.respect_robots_txt",
    "limits.max_pages", "limits.max_records", "limits.max_requests", "limits.max_seconds",
    "limits.delay_seconds", "limits.timeout_seconds", "limits.max_retries", "limits.max_clicks",
    "limits.max_scrolls", "diagnosis.max_requests", "diagnosis.render_with_browser",
    "extraction.method", "extraction.record_selector", "extraction.table_selector",
    "extraction.records_path", "extraction.file_format", "extraction.deduplicate_on",
    "extraction.drop_invalid", "extraction.keep_raw",
    "extraction.pagination.mode", "extraction.pagination.next_selector", "extraction.pagination.url_template",
    "extraction.pagination.page_param", "extraction.pagination.start_page", "extraction.pagination.next_field",
    "extraction.browser.wait_selector", "extraction.browser.load_more_selector",
    "extraction.browser.infinite_scroll", "extraction.browser.wait_timeout_seconds",
    "extraction.api.documented", "extraction.api.documentation_url",
    "auth.type", "auth.login_url", "auth.username_field", "auth.password_field",
    "auth.username_env", "auth.password_env", "auth.failure_text",
    "auth.header_name", "auth.header_prefix", "auth.token_env", "output.formats",
]
DEFAULTS_UA = default_config_dict("https://www.example.org/")["user_agent"]
LIST_TEXT_WIDGETS = ["scope.allowed_domains", "scope.allowed_path_prefixes"]
NULLABLE_WIDGETS = {"authorization.valid_until", "extraction.file_format"}
VERBATIM_TEXT = {"auth.header_prefix"}  # «Bearer » lleva el espacio como separador
NON_NULL_TEXT = {"project.description": "", "user_agent": DEFAULTS_UA, "extraction.pagination.page_param": "page",
                 "auth.username_field": "username", "auth.password_field": "password",
                 "auth.header_name": "Authorization", "auth.header_prefix": ""}
DEFAULTS = default_config_dict("https://www.example.org/")
DEFAULTS["extraction"].update({
    "record_selector": None, "table_selector": None, "records_path": None, "file_format": None,
    "deduplicate_on": [], "drop_invalid": False, "keep_raw": True,
    "pagination": {"mode": "none", "next_selector": None, "url_template": None, "page_param": "page",
                   "start_page": 1, "next_field": None},
    "browser": {"wait_selector": None, "load_more_selector": None, "infinite_scroll": False,
                "wait_timeout_seconds": 10.0},
    "api": {"documented": False, "documentation_url": None},
})
DEFAULTS["auth"].update({"login_url": None, "username_field": "username", "password_field": "password",
                         "username_env": None, "password_env": None, "failure_text": None,
                         "header_name": "Authorization", "header_prefix": "Bearer ", "token_env": None})


# --------------------------------------------------------------------------- utilidades
def get_path(data: dict, path: str, default: Any = None) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def set_path(data: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def wkey(path: str) -> str:
    return f"w:{path}"


def load_into_state(data: dict) -> None:
    """Vuelca un diccionario de configuración en los widgets. Solo llamar desde callbacks."""
    merged = deep_merge(DEFAULTS, data)
    for path in SIMPLE_WIDGETS:
        value = get_path(merged, path)
        if path == "authorization.valid_until" and isinstance(value, str):
            value = date.fromisoformat(value)
        if path in ("extraction.browser.wait_timeout_seconds", "limits.delay_seconds",
                    "limits.max_seconds", "limits.timeout_seconds") and value is not None:
            value = float(value)
        if value is None and path not in NULLABLE_WIDGETS:
            value = ""
        st.session_state[wkey(path)] = value
    for path in LIST_TEXT_WIDGETS:
        st.session_state[wkey(path)] = ", ".join(get_path(merged, path) or [])
    st.session_state["fields_rows"] = fields_to_rows(get_path(merged, "extraction.fields") or [])
    st.session_state["fields_version"] = st.session_state.get("fields_version", 0) + 1
    for key in ("diagnosis", "preview", "suggestion"):
        st.session_state.pop(key, None)


def collect() -> dict:
    data: dict = {}
    for path in SIMPLE_WIDGETS:
        value = st.session_state.get(wkey(path), get_path(DEFAULTS, path))
        if isinstance(value, str) and path not in VERBATIM_TEXT:
            value = value.strip() or NON_NULL_TEXT.get(path)
        if isinstance(value, date):
            value = value.isoformat()
        set_path(data, path, value)
    for path in LIST_TEXT_WIDGETS:
        text = st.session_state.get(wkey(path)) or ""
        set_path(data, path, [p.strip() for p in text.split(",") if p.strip()])
    edited = st.session_state.get("fields_current")
    rows = edited.to_dict(orient="records") if isinstance(edited, pd.DataFrame) else st.session_state.get("fields_rows", [])
    rows = [{k: v for k, v in row.items() if k != "usar"} for row in rows if row.get("usar", True) is not False]
    data["extraction"]["fields"] = rows_to_fields(rows)
    names = {f["name"] for f in data["extraction"]["fields"]}
    data["extraction"]["deduplicate_on"] = [d for d in data["extraction"].get("deduplicate_on") or [] if d in names]
    data["version"] = 1
    data["output"]["directory"] = str(ROOT / "outputs")
    if diagnosis_only():
        data["authorization"].update(confirmed=False, authorized_by=DIAG_ONLY_BY, purpose=DIAG_ONLY_PURPOSE,
                                     evidence_reference=None)
    derive_limits(data)
    auth_type = data["auth"]["type"]
    if auth_type == "none":
        data["auth"] = {"type": "none"}
    elif auth_type == "form":
        data["auth"] = {k: v for k, v in data["auth"].items() if k not in ("header_name", "header_prefix", "token_env")}
    else:
        data["auth"] = {k: data["auth"].get(k) for k in ("type", "header_name", "header_prefix", "token_env")}
    return data


DIAG_ONLY_BY = "Nadie: solo diagnóstico pasivo, sin extracción"
DIAG_ONLY_PURPOSE = "Identificar los mecanismos de protección del sitio sin extraer datos"


def diagnosis_only() -> bool:
    return st.session_state.get("mode") == "diagnostico"


def derive_limits(data: dict) -> None:
    """La interfaz solo pide páginas, registros y pausa; el resto de topes se deriva de ellos."""
    lim = data["limits"]
    pages = int(lim.get("max_pages") or 1)
    delay = float(lim.get("delay_seconds") or 1.0)
    lim["max_requests"] = pages + 3
    lim["max_clicks"] = lim["max_scrolls"] = max(pages - 1, 0)
    lim["max_seconds"] = float(min(3600, pages * (delay + float(lim.get("timeout_seconds") or 20)) + 60))
    if data["auth"]["type"] != "none":
        data["authorization"]["allow_authentication"] = True
    data["authorization"]["terms_reviewed"] = bool(data["authorization"].get("confirmed"))


def validate(data: dict) -> tuple[ProjectConfig | None, list[str]]:
    try:
        return parse_config(data), []
    except ConfigError as exc:
        return None, exc.messages


def example_catalog() -> dict[str, Path]:
    catalog = {}
    for path in sorted(EXAMPLES.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        label = (raw.get("project") or {}).get("description") or path.stem
        catalog[f"{path.stem} — {label}"] = path
    return catalog


def _same_page(a: str, b: str) -> bool:
    x, y = urlsplit(a), urlsplit(b)
    return (x.netloc.lower(), x.path.rstrip("/"), x.query) == (y.netloc.lower(), y.path.rstrip("/"), y.query)


def previous_config(url: str) -> tuple[dict, str] | None:
    """Configuración de la última ejecución sobre esta misma URL (perfil reutilizable), si existe."""
    found = []
    for path in (ROOT / "outputs").glob("*/*/config_efectiva.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _same_page(data.get("target_url") or "", url):
            found.append((path.parent.name, data))
    if not found:
        return None
    run_id, data = max(found, key=lambda item: item[0])
    data["authorization"]["confirmed"] = False
    return data, run_id


# ----------------------------------------------------------------------------- callbacks
def cb_new_from_url() -> None:
    url = (st.session_state.get("start_url") or "").strip()
    if not url:
        st.session_state["flash"] = ("warning", "Escriba una URL para empezar.")
        return
    if "://" not in url:
        url = "https://" + url
    known = previous_config(url)
    load_into_state(known[0] if known else default_config_dict(url))
    st.session_state["started"] = True
    if known:
        st.session_state["flash"] = ("info", f"Sitio ya analizado: se recuperó la configuración de la ejecución "
                                             f"{known[1]} (campos, método y límites). Vuelva a confirmar la autorización; "
                                             "al extraer se compara con el perfil anterior para detectar cambios.")
    else:
        st.session_state["flash"] = ("info", "Complete la autorización; hasta entonces no se hace ninguna "
                                             "solicitud al sitio.")


def cb_load_example() -> None:
    choice = st.session_state.get("example_choice")
    if not choice:
        return
    path = example_catalog()[choice]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        data = parse_config(raw).model_dump(by_alias=True, mode="json")
    except ConfigError as exc:
        data = raw
        st.session_state["flash"] = ("error", "El ejemplo es inválido a propósito:\n- " + "\n- ".join(exc.messages))
    else:
        st.session_state["flash"] = ("success", f"Ejemplo «{path.stem}» cargado.")
    load_into_state(data)
    st.session_state["started"] = True


def apply_suggestion(suggestion: dict) -> None:
    for key in ("record_selector", "table_selector", "records_path", "file_format"):
        st.session_state[wkey(f"extraction.{key}")] = suggestion.get(key) or (None if key == "file_format" else "")
    st.session_state[wkey("extraction.method")] = suggestion["method"]
    pagination = suggestion.get("pagination") or {"mode": "none"}
    st.session_state[wkey("extraction.pagination.mode")] = pagination["mode"]
    for key in ("next_selector", "url_template", "next_field"):
        st.session_state[wkey(f"extraction.pagination.{key}")] = pagination.get(key) or ""
    st.session_state["fields_rows"] = fields_to_rows(suggestion["fields"])
    st.session_state["fields_version"] = st.session_state.get("fields_version", 0) + 1


def cb_diagnose() -> None:
    cfg, errors = validate(collect())
    if cfg is None:
        st.session_state["flash"] = ("error", "Corrija la configuración antes de diagnosticar.")
        return
    try:
        diagnosis = ExtractionEngine(cfg).diagnose()
    except (AuthorizationError, WebExtractorError) as exc:
        st.session_state["flash"] = ("error", str(exc))
        return
    st.session_state.pop("preview", None)
    st.session_state["diagnosis"] = diagnosis
    suggestion = suggest_extraction(diagnosis) if not diagnosis.stopped else None
    st.session_state["suggestion"] = suggestion
    if suggestion and (st.session_state.get(wkey("extraction.method")) or "auto") == "auto":
        apply_suggestion(suggestion)
        st.session_state["flash"] = ("success", f"Diagnóstico listo: se propusieron {len(suggestion['fields'])} campos. "
                                                "Revíselos en «Datos a extraer» y pulse «Vista previa».")
    elif suggestion:
        st.session_state["flash"] = ("success", "Diagnóstico listo. Se conservaron los campos que ya tenía; si prefiere "
                                                "los sugeridos, use «Usar los campos sugeridos por el diagnóstico».")


def cb_apply_suggestion() -> None:
    if st.session_state.get("suggestion"):
        apply_suggestion(st.session_state["suggestion"])
        st.session_state["flash"] = ("success", "Campos sugeridos aplicados. Revíselos antes de la vista previa.")


def cb_start_job(cfg: ProjectConfig) -> None:
    current: ExtractionJob | None = st.session_state.get("job")
    if current and current.running:
        return
    st.session_state["job"] = ExtractionJob(cfg).start()


def cb_reset() -> None:
    for key in list(st.session_state.keys()):
        if key != "start_url":
            del st.session_state[key]


# --------------------------------------------------------------------------------- vistas
def only_login_barrier(diagnosis) -> bool:
    """Un 401/inicio de sesión no impide seguir si el propietario dio credenciales; CAPTCHA o bloqueos sí."""
    return bool(diagnosis.incidents) and all(i.kind == "auth_required" for i in diagnosis.incidents)


def login_detected(diagnosis) -> bool:
    return diagnosis is not None and (any(i.kind == "auth_required" for i in diagnosis.incidents)
                                      or any(f.code == "html.login_form" for f in diagnosis.findings))


def section(number: int, title: str, done: bool = False):
    box = st.container(border=True)
    box.markdown(f"### {'✅' if done else f'{number}.'} {title}")
    return box


def render_test_examples() -> None:
    """Solo con WE_GUI_EXAMPLES_DIR definido (pruebas automáticas): cargar una configuración guardada."""
    if not os.environ.get("WE_GUI_EXAMPLES_DIR"):
        return
    with st.sidebar:
        st.selectbox("Ejemplo", list(example_catalog()), index=None, key="example_choice")
        st.button("Cargar", on_click=cb_load_example)


def render_welcome() -> None:
    st.title("Proyecto final_TAD")
    st.markdown("Herramienta que **analiza cómo un sitio web entrega su información**, recomienda cómo obtenerla "
                "y **extrae los datos que usted elija**, limpios y con su origen, solo con autorización.")
    with section(1, "¿Qué sitio quiere analizar?"), st.form("start_form", border=False):
        cols = st.columns([4, 1], vertical_alignment="bottom")
        cols[0].text_input("URL del sitio", key="start_url", placeholder="https://www.datos.gob.mx/dataset/")
        cols[1].form_submit_button("Comenzar", type="primary", on_click=cb_new_from_url, width="stretch")
        st.caption("No se hace ninguna solicitud al sitio hasta que usted complete la autorización.")
        flash = st.session_state.pop("flash", None)
        if flash:
            getattr(st, flash[0])(flash[1])


def render_top(data: dict) -> None:
    cols = st.columns([5, 1], vertical_alignment="center")
    cols[0].markdown(f"## {urlsplit(data.get('target_url') or '').netloc}")
    cols[0].caption(data.get("target_url") or "")
    cols[1].button("Analizar otra URL", on_click=cb_reset, width="stretch")
    flash = st.session_state.pop("flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])


def authorization_missing(cfg: ProjectConfig) -> list[str]:
    a = cfg.authorization
    missing = [m for m in missing_for_diagnosis(cfg) if "expiró" in m]
    if not a.authorized_by:
        missing.append("quién autoriza")
    if not a.purpose:
        missing.append("para qué usará los datos")
    if a.environment == "production" and not a.evidence_reference:
        missing.append("el permiso o la licencia")
    if not a.confirmed:
        missing.append("marcar la confirmación")
    return missing


AUTHORIZERS = [
    "Propietario del sitio",
    "Licencia de datos abiertos del sitio",
    "Institución pública que publica los datos",
    "Docente o institución académica",
    "Cliente o contratante del proyecto",
]
PURPOSES = [
    "Uso educativo (proyecto académico)",
    "Investigación",
    "Análisis estadístico",
    "Periodismo de datos",
    "Uso interno de la organización",
]
LICENSES = [
    "Licencia de Libre Uso MX (datos abiertos)",
    "Creative Commons CC BY 4.0",
    "Creative Commons CC0 (dominio público)",
    "Open Data Commons ODbL",
    "Términos de uso del sitio que permiten la reutilización",
    "Permiso escrito del propietario (correo o contrato)",
    "Convenio académico o institucional",
]


def combo(container, label: str, path: str, options: list[str], placeholder: str = "Elija una opción o escriba otra"):
    """Lista desplegable que también acepta un valor escrito (y conserva el de una configuración recuperada)."""
    key = wkey(path)
    current = st.session_state.get(key) or None
    st.session_state[key] = current
    container.selectbox(label, options + ([current] if current and current not in options else []),
                        key=key, accept_new_options=True, placeholder=placeholder)


def step_authorization(cfg: ProjectConfig | None, errors: list[str]) -> bool:
    missing = authorization_missing(cfg) if cfg else ["corregir la configuración"]
    only = diagnosis_only()
    with section(2, "Autorización", done=only or not missing):
        st.radio("¿Qué quiere hacer?", ["extraer", "diagnostico"], key="mode", horizontal=True,
                 format_func={"extraer": "Extraer datos (tengo autorización)",
                              "diagnostico": "Solo diagnosticar (no tengo autorización para extraer)"}.get)
        if only:
            st.info("**Solo diagnóstico.** Se hacen pocas solicitudes, se respeta robots.txt y se identifican las "
                    "tecnologías y protecciones del sitio (CAPTCHA, anti-bot, inicio de sesión…). **No se extraen "
                    "datos.** Para extraer necesita autorización del propietario o una licencia.",
                    icon=":material/policy:")
            for message in errors:
                st.error(message)
            return cfg is not None
        st.caption("Solo se trabaja con sitios y datos cuyo uso esté permitido. Indique quién lo permite y para qué.")
        c1, c2 = st.columns(2)
        combo(c1, "¿Quién autoriza el uso?", "authorization.authorized_by", AUTHORIZERS)
        combo(c2, "Permiso o licencia de uso", "authorization.evidence_reference", LICENSES,
              "Elija una opción o escriba otra (p. ej. un enlace)")
        combo(st, "¿Para qué usará los datos?", "authorization.purpose", PURPOSES)
        st.checkbox("Confirmo que tengo autorización y que revisé los términos de uso del sitio",
                    key=wkey("authorization.confirmed"))
        for message in errors:
            st.error(message)
        if missing and cfg is not None:
            st.caption("Falta: " + "; ".join(missing))
    return not missing


def step_diagnosis(cfg: ProjectConfig):
    diagnosis = st.session_state.get("diagnosis")
    with section(3, "Diagnóstico del sitio", done=diagnosis is not None and not diagnosis.stopped):
        st.caption(f"Revisa con pocas solicitudes (máximo {cfg.diagnosis.max_requests}) cómo entrega los datos el sitio: "
                   "HTML, JavaScript, API, archivos, paginación, carga dinámica, inicio de sesión, CAPTCHA o bloqueos.")
        st.button("Diagnosticar sitio", type="primary", on_click=cb_diagnose)
        if diagnosis is None:
            return None
        for incident in diagnosis.incidents:
            show_incident(incident, diagnosis.files.get("intervention"))
        if login_detected(diagnosis) and not any(i.kind == "auth_required" for i in diagnosis.incidents):
            st.info(AUTH_HINT, icon=":material/key:")
        best = diagnosis.best
        if best is not None and not diagnosis.stopped:
            st.success(f"**Estrategia recomendada: {METHODS.get(best.method, best.method)}** "
                       f"(confianza {best.confidence}). " + " ".join(f"✓ {r}" for r in best.reasons[:3]))
        if diagnosis.findings:
            st.markdown("**Tecnologías y mecanismos detectados**")
            for f in diagnosis.findings[:12]:
                st.markdown(f"- **{f.category}:** {f.message}")
        st.download_button("Descargar informe del diagnóstico", diagnosis_markdown(diagnosis),
                           file_name="diagnostico.md", mime="text/markdown")
        if diagnosis.files.get("folder"):
            st.caption(f"Registro del diagnóstico (informe, bitácora de acciones y log): `{diagnosis.files['folder']}`")
    return diagnosis


def show_incident(incident, recorded_in: str | None = None) -> None:
    """Barrera con lo que debe hacer una persona, si se puede continuar y dónde quedó registrada."""
    guide = guide_for(incident.kind)
    body = (f"**Barrera detectada: {incident.kind}** — {incident.message}\n\n"
            f"**Siguiente paso legítimo:** {incident.next_step}")
    if guide:
        body += f"\n\n**¿Se puede continuar?** {guide['answer']}\n\n**Qué hacer:**\n" + "\n".join(
            f"{n}. {step}" for n, step in enumerate(guide["steps"], 1))
    if recorded_in:
        body += (f"\n\nRegistrado en `{recorded_in}` y en el registro central "
                 f"`{ROOT / 'outputs' / INTERVENTION_LOG}`.")
    blocking = guide is None or guide["can_continue"] in ("no", "mas_tarde")
    (st.error if blocking else st.warning)(body, icon=":material/block:" if blocking else ":material/key:")


AUTH_HINT = ("El sitio pide iniciar sesión. Solo continúe si el propietario le dio una cuenta o un token: "
             "configúrelo en el paso 5 («Acceso autorizado»). La herramienta no evade inicios de sesión.")
BASIC_FIELD_COLUMNS = {"html": ["usar", "name", "selector", "attribute", "type"],
                       "table": ["usar", "name", "column", "type"],
                       "path": ["usar", "name", "path", "type"]}


def step_fields(cfg: ProjectConfig) -> None:
    preview = st.session_state.get("preview")
    with section(4, "Datos a extraer", done=bool(preview and preview.records)):
        st.caption("Marque los campos que necesita. Puede cambiar el nombre, el selector o el tipo, o añadir filas.")
        suggestion = st.session_state.get("suggestion")
        if suggestion and fields_to_rows(suggestion["fields"]) != st.session_state.get("fields_rows"):
            st.button(f"Usar los campos sugeridos por el diagnóstico ({len(suggestion['fields'])})", on_click=cb_apply_suggestion)
        method = st.session_state.get(wkey("extraction.method")) or "auto"
        kind = ("table" if st.session_state.get(wkey("extraction.table_selector"))
                else "path" if method in ("api", "structured_file") else "html")
        rules = st.toggle("Mostrar reglas de limpieza y validación", key="fields_advanced")
        rows = [{"usar": True, **r} for r in st.session_state.get("fields_rows") or []]
        frame = pd.DataFrame(rows, columns=["usar", *FIELD_COLUMNS])
        frame["usar"] = frame["usar"].fillna(True).astype(bool)
        order = BASIC_FIELD_COLUMNS[kind] + (["required", "normalize", "pattern", "date_format", "regex", "min", "max",
                                              "choices"] if rules else [])
        edited = st.data_editor(
            frame, key=f"fields_editor_{st.session_state.get('fields_version', 0)}", num_rows="dynamic",
            hide_index=True, width="stretch", column_order=order,
            column_config={
                "usar": st.column_config.CheckboxColumn("Extraer", width="small"),
                "name": st.column_config.TextColumn("Campo", required=True),
                "selector": st.column_config.TextColumn("Selector CSS"),
                "attribute": st.column_config.TextColumn("Atributo", help="text (por defecto), href, src, data-…"),
                "column": st.column_config.TextColumn("Columna de la tabla"),
                "path": st.column_config.TextColumn("Ruta (JSON/XML/CSV)"),
                "type": st.column_config.SelectboxColumn("Tipo", options=list(SUPPORTED_TYPES), required=True),
                "required": st.column_config.CheckboxColumn("Obligatorio"),
                "normalize": st.column_config.MultiselectColumn("Limpieza", options=sorted(NORMALIZERS)),
                "pattern": st.column_config.TextColumn("Patrón (regex)"),
                "date_format": st.column_config.TextColumn("Formato fecha"),
                "regex": st.column_config.TextColumn("Validar regex"),
                "min": st.column_config.NumberColumn("Mín."),
                "max": st.column_config.NumberColumn("Máx."),
                "choices": st.column_config.TextColumn("Valores permitidos", help="Separados por coma"),
            })
        st.session_state["fields_current"] = edited
        with st.expander("¿No aparecen los registros correctos? Cambiar el selector"):
            if kind == "path":
                st.text_input("Ruta a la lista de registros", key=wkey("extraction.records_path"), placeholder="data.items")
            else:
                st.text_input("Selector de cada registro (CSS)", key=wkey("extraction.record_selector"),
                              placeholder="article.producto")
                st.text_input("…o selector de una tabla", key=wkey("extraction.table_selector"), placeholder="table#datos")
        if st.button("Vista previa", type="primary", disabled=cfg.extraction.method == "auto"):
            with st.spinner("Obteniendo una página…"):
                try:
                    st.session_state["preview"] = ExtractionEngine(cfg).preview(max_records=10)
                except WebExtractorError as exc:
                    st.error(str(exc))
                else:
                    st.rerun()
        preview = st.session_state.get("preview")
        if preview is not None:
            for incident in preview.incidents:
                show_incident(incident, preview.files.get("intervention"))
            show_records(preview.records, preview.quality)


def step_config(cfg: ProjectConfig, errors: list[str]) -> None:
    job: ExtractionJob | None = st.session_state.get("job")
    with section(5, "Configuración y ejecución de la extracción", done=current_result() is not None):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            choices = [m for m in METHODS if m != "auto"]
            if st.session_state.get(wkey("extraction.method")) not in choices:
                best = getattr(st.session_state.get("diagnosis"), "best", None)
                st.session_state[wkey("extraction.method")] = best.method if best and best.method in choices else "static_html"
            st.selectbox("Estrategia de extracción", choices, format_func=METHODS.get,
                         key=wkey("extraction.method"), help="La recomendada por el diagnóstico ya está elegida.")
            method = st.session_state.get(wkey("extraction.method"))
            modes = {"static_html": ["none", "next_link", "url_template"], "browser": ["none", "next_link"],
                     "api": ["none", "next_field", "page_param"]}.get(method, ["none"])
            if st.session_state.get(wkey("extraction.pagination.mode")) not in modes:
                st.session_state[wkey("extraction.pagination.mode")] = "none"
            st.selectbox("Paginación", modes, key=wkey("extraction.pagination.mode"), format_func={
                "none": "Sin paginación", "next_link": "Enlace «siguiente»", "url_template": "Número de página en la URL",
                "next_field": "Campo «siguiente» en la respuesta", "page_param": "Parámetro de página"}.get)
            mode = st.session_state.get(wkey("extraction.pagination.mode"))
            if mode == "next_link":
                st.text_input("Selector del enlace «siguiente»", key=wkey("extraction.pagination.next_selector"),
                              placeholder="a[rel=next]")
            elif mode == "url_template":
                st.text_input("URL con {page} donde va el número", key=wkey("extraction.pagination.url_template"))
            elif mode == "next_field":
                st.text_input("Ruta del campo «siguiente»", key=wkey("extraction.pagination.next_field"), placeholder="links.next")
            elif mode == "page_param":
                st.text_input("Nombre del parámetro", key=wkey("extraction.pagination.page_param"))
            if method == "browser":
                st.text_input("Botón «cargar más» (opcional)", key=wkey("extraction.browser.load_more_selector"),
                              placeholder="#load-more")
                st.checkbox("La página carga más al hacer scroll", key=wkey("extraction.browser.infinite_scroll"))
            if method == "api":
                st.checkbox("La API es pública y está documentada por el propietario", key=wkey("extraction.api.documented"))
                st.text_input("Enlace a la documentación", key=wkey("extraction.api.documentation_url"))
        with c2:
            a, b = st.columns(2)
            a.number_input("Páginas máx.", 1, 100, key=wkey("limits.max_pages"),
                           help="Con «cargar más» o scroll, cada carga adicional cuenta como una página.")
            b.number_input("Registros máx.", 1, 10_000, key=wkey("limits.max_records"))
            a.number_input("Pausa entre solicitudes (s)", 0.0, 60.0, key=wkey("limits.delay_seconds"), step=0.5,
                           help="Mínimo 1 s en sitios reales; si robots.txt pide más, se respeta.")
            st.multiselect("Formatos de salida", ["csv", "excel", "json", "sqlite"], key=wkey("output.formats"))
        if st.session_state.get(wkey("auth.type"), "none") != "none" or login_detected(st.session_state.get("diagnosis")):
            show_auth()
        for message in [e for e in errors if not e.startswith("authorization")]:
            st.error(message)
        for message in missing_for_extraction(cfg):
            if message.startswith("API "):
                st.warning("Para usar la API marque que es pública y documentada e indique el enlace a su documentación.")
            elif message.startswith("authorization.allow_authentication"):
                st.warning("Confirme el acceso autorizado con cuenta o token.")
        running = bool(job and job.running)
        st.button("Iniciar extracción", type="primary", disabled=running or cfg.extraction.method == "auto",
                  on_click=cb_start_job, args=(cfg,))
        if job:
            job_panel()


def show_auth() -> None:
    with st.expander("Acceso autorizado (solo si el propietario le dio una cuenta o un token)", expanded=True):
        st.selectbox("Tipo", ["none", "form", "header"], key=wkey("auth.type"),
                     format_func={"none": "Sin acceso con cuenta", "form": "Usuario y contraseña",
                                  "header": "Token o API key documentado"}.get)
        st.caption("Las credenciales no se escriben aquí: indique el nombre de la variable de entorno que las contiene.")
        kind = st.session_state.get(wkey("auth.type"))
        names = []
        if kind == "form":
            st.text_input("Página de inicio de sesión", key=wkey("auth.login_url"))
            c1, c2 = st.columns(2)
            c1.text_input("Variable con el usuario", key=wkey("auth.username_env"), placeholder="WE_USUARIO")
            c2.text_input("Variable con la contraseña", key=wkey("auth.password_env"), placeholder="WE_CLAVE")
            c1.text_input("Nombre del campo de usuario en el formulario", key=wkey("auth.username_field"),
                          help="Atributo name del campo: username, email, user…")
            c2.text_input("Nombre del campo de contraseña", key=wkey("auth.password_field"))
            names = [wkey("auth.username_env"), wkey("auth.password_env")]
        elif kind == "header":
            c1, c2 = st.columns(2)
            c1.text_input("Encabezado", key=wkey("auth.header_name"))
            c2.text_input("Variable con el token", key=wkey("auth.token_env"), placeholder="MI_API_TOKEN")
            names = [wkey("auth.token_env")]
        for key in names:
            name = st.session_state.get(key)
            if name:
                defined = bool(os.environ.get(name))
                st.caption(f"{'✓' if defined else '✗'} `{name}` {'definida' if defined else 'no definida en este proceso'}")


def show_records(records, quality) -> None:
    if not records:
        st.warning("No se encontraron registros. Revise el selector de registros o, si el contenido se genera con "
                   "JavaScript, elija la estrategia Navegador en el paso 5.")
        return
    rows = [{"estado": r.lineage["validation_status"], **r.data,
             "errores": "; ".join(r.lineage["validation_errors"])} for r in records]
    st.dataframe(pd.DataFrame(rows, dtype=object).fillna("—").astype(str), hide_index=True, width="stretch")
    m = st.columns(4)
    m[0].metric("Válidos", quality.valid)
    m[1].metric("Con advertencia", quality.with_warnings)
    m[2].metric("Inválidos", quality.invalid)
    m[3].metric("Duplicados eliminados", quality.duplicates_removed)


def current_result():
    job: ExtractionJob | None = st.session_state.get("job")
    if job and not job.running and job.result:
        return job.result
    return st.session_state.get("last_result")


@st.fragment(run_every=1.0)
def job_panel() -> None:
    job: ExtractionJob | None = st.session_state.get("job")
    if job is None:
        return
    counters = job.counters()
    top = st.columns([3, 1], vertical_alignment="center")
    if job.running:
        top[0].markdown(f"**Extrayendo…** {job.elapsed:.0f} s · {counters['solicitudes']} solicitudes · "
                        f"{counters['paginas']} páginas · {counters['registros']} registros")
        top[1].button("Cancelar", on_click=job.request_cancel, width="stretch")
    if job.error:
        st.error(job.error)
    if not job.running and not st.session_state.get("job_reported") is job:
        st.session_state["job_reported"] = job
        if job.result:
            st.session_state["last_result"] = job.result
        st.rerun(scope="app")


def step_results(result) -> None:
    with section(6, "Resultados"):
        style = STATUS_STYLE.get(result.status, "info")
        getattr(st, style)(f"**{result.status}** — {STATUS_TEXT.get(result.status, '')}\n\n{result.status_message}")
        if result.requires_human_review:
            st.warning("**La estructura del sitio cambió** respecto a la ejecución anterior; revise los campos.",
                       icon=":material/rule:")
        show_records(result.records, result.quality)
        q = result.quality
        st.markdown("**Calidad por campo**")
        st.dataframe(pd.DataFrame([{"Campo": name, "Con valor": fq.filled, "Vacíos": fq.empty, "Errores": fq.invalid,
                                    "Llenado": fq.fill_rate(q.total_raw)} for name, fq in q.fields.items()]),
                     hide_index=True, width="stretch",
                     column_config={"Llenado": st.column_config.ProgressColumn("Llenado", min_value=0, max_value=1,
                                                                               format="percent")})
        if result.incidents or result.profile_changes:
            st.markdown("**Errores, incidencias y cambios detectados**")
            for i in result.incidents:
                if guide_for(i.kind):
                    show_incident(i, result.outputs.get("intervention"))
                else:
                    st.markdown(f"- **{i.kind}:** {i.message}  \n  _Siguiente paso:_ {i.next_step}")
            for c in result.profile_changes:
                st.markdown(f"- Cambio **{c['severity']}** · {c['kind']}: {c['message']}")
        cols = st.columns(4)
        downloads = [("csv", "CSV", "text/csv"),
                     ("excel", "Excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                     ("json", "JSON", "application/json"), ("report", "Informe final", "text/markdown")]
        for col, (key, label, mime) in zip(cols, downloads):
            path = result.outputs.get(key)
            if path and Path(path).exists():
                col.download_button(label, Path(path).read_bytes(), file_name=Path(path).name, mime=mime,
                                    width="stretch", key=f"dl_{key}")
        st.caption(f"Cada registro guarda su origen (URL, fecha, método, campo, validación, transformaciones y "
                   f"ejecución {result.run_id}). Archivos completos en `{result.run_dir}`"
                   + (f"; base SQLite `{result.outputs['sqlite']}`." if result.outputs.get("sqlite") else ".")
                   + f" Log de esta ejecución: `run.log`; bitácora de acciones: `actions.jsonl`; log general de la "
                   f"herramienta: `{ROOT / 'outputs' / GENERAL_LOG}`.")


def main() -> None:
    st.set_page_config(page_title="Proyecto final_TAD", page_icon=":material/travel_explore:", layout="centered")
    render_test_examples()
    if not st.session_state.get("started"):
        render_welcome()
        return
    data = collect()
    cfg, errors = validate(data)
    render_top(data)
    authorized = step_authorization(cfg, errors if cfg is None else [e for e in errors if e.startswith("authorization")])
    if not authorized or cfg is None:
        return
    diagnosis = step_diagnosis(cfg)
    if diagnosis is not None and diagnosis_only():
        st.info("**Extracción bloqueada: modo solo diagnóstico.** Para extraer datos de este sitio use una vía "
                "autorizada por el propietario (API documentada, descarga oficial, licencia o permiso por escrito) "
                "y elija «Extraer datos» en Autorización.", icon=":material/lock:")
        return
    if diagnosis is None or (diagnosis.stopped and not only_login_barrier(diagnosis)):
        return
    step_fields(cfg)
    step_config(cfg, errors)
    result = current_result()
    if result is not None:
        step_results(result)


if __name__ == "__main__":
    main()
