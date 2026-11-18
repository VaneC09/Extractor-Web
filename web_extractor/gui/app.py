"""Interfaz gráfica local del extractor (Streamlit).

Ejecutar con ``python -m web_extractor gui``. Recorre el mismo flujo que la CLI: proyecto y
autorización → alcance y límites → diagnóstico → campos → vista previa → extracción → resultados.
Todas las acciones que generan solicitudes pasan por las mismas puertas de autorización del motor.
"""

from __future__ import annotations

import copy
import json
import os
import socket
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
from web_extractor.devtools.fixture_server import DEFAULT_API_TOKEN, DEFAULT_PASSWORD, DEFAULT_USER, FixtureServer
from web_extractor.gui.jobs import ExtractionJob
from web_extractor.reports.diagnosis_report import diagnosis_markdown
from web_extractor.reports.run_report import STATUS_TEXT
from web_extractor.selection.suggest import suggest_extraction
from web_extractor.transforms.casting import SUPPORTED_TYPES
from web_extractor.transforms.normalizers import NORMALIZERS

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
FIXTURE_PORT = int(os.environ.get("WE_GUI_FIXTURE_PORT", "8765"))

METHODS = {
    "auto": "Automático (solo diagnóstico)",
    "static_html": "HTML estático (Requests + BeautifulSoup)",
    "browser": "Navegador (Selenium)",
    "structured_file": "Archivo CSV/JSON descargable",
    "api": "API pública documentada",
}
ENVIRONMENTS = {"fixture": "Fixture local controlado", "test": "Entorno de prueba", "production": "Sitio real"}
STATUS_STYLE = {
    "completado": "success", "completado_con_limites": "info", "parcial_barrera": "warning",
    "detenido_barrera": "error", "detenido_politica": "error", "cancelado": "warning", "fallido": "error",
}
CONFIDENCE_COLOR = {"alta": "green", "media": "orange", "baja": "gray"}

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
    data["extraction"]["fields"] = rows_to_fields(rows)
    names = {f["name"] for f in data["extraction"]["fields"]}
    data["extraction"]["deduplicate_on"] = [d for d in data["extraction"].get("deduplicate_on") or [] if d in names]
    data["version"] = 1
    data["output"]["directory"] = str(ROOT / "outputs")
    auth_type = data["auth"]["type"]
    if auth_type == "none":
        data["auth"] = {"type": "none"}
    elif auth_type == "form":
        data["auth"] = {k: v for k, v in data["auth"].items() if k not in ("header_name", "header_prefix", "token_env")}
    else:
        data["auth"] = {k: data["auth"].get(k) for k in ("type", "header_name", "header_prefix", "token_env")}
    return data


def validate(data: dict) -> tuple[ProjectConfig | None, list[str]]:
    try:
        return parse_config(data), []
    except ConfigError as exc:
        return None, exc.messages


def exportable_yaml(data: dict) -> str:
    clean = copy.deepcopy(data)
    clean["output"]["directory"] = "outputs"
    return "# Generado por la interfaz gráfica de Proyecto final_TAD\n" + yaml.safe_dump(clean, allow_unicode=True, sort_keys=False)


# ------------------------------------------------------------------ servidor de fixtures
def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@st.cache_resource(show_spinner=False)
def fixture_server() -> tuple[FixtureServer | None, str]:
    os.environ.setdefault("WE_FIXTURE_USER", DEFAULT_USER)
    os.environ.setdefault("WE_FIXTURE_PASSWORD", DEFAULT_PASSWORD)
    os.environ.setdefault("WE_FIXTURE_API_TOKEN", DEFAULT_API_TOKEN)
    base = f"http://127.0.0.1:{FIXTURE_PORT}"
    os.environ["FIXTURE_BASE_URL"] = base
    if _port_open(FIXTURE_PORT):
        return None, f"Usando el sitio de pruebas que ya se está ejecutando en {base}"
    server = FixtureServer("127.0.0.1", FIXTURE_PORT).start()
    return server, f"Sitio de pruebas iniciado en {base}"


def example_catalog() -> dict[str, Path]:
    catalog = {}
    for path in sorted(EXAMPLES.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        label = (raw.get("project") or {}).get("description") or path.stem
        catalog[f"{path.stem} — {label}"] = path
    return catalog


# ----------------------------------------------------------------------------- callbacks
def cb_new_from_url() -> None:
    url = (st.session_state.get("start_url") or "").strip()
    if not url:
        st.session_state["flash"] = ("warning", "Escriba una URL para empezar.")
        return
    if "://" not in url:
        url = "https://" + url
    load_into_state(default_config_dict(url))
    st.session_state["started"] = True
    st.session_state["flash"] = ("success", "Configuración inicial creada. Complete la autorización antes de "
                                            "cualquier solicitud al sitio.")


def cb_load_example() -> None:
    choice = st.session_state.get("example_choice")
    if not choice:
        return
    fixture_server()
    st.session_state["fixtures_on"] = True
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


def cb_upload_config() -> None:
    upload = st.session_state.get("config_upload")
    if upload is None:
        return
    try:
        raw = yaml.safe_load(upload.getvalue().decode("utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        st.session_state["flash"] = ("error", f"No se pudo leer el archivo: {exc}")
        return
    load_into_state(raw if isinstance(raw, dict) else {})
    st.session_state["started"] = True
    st.session_state["flash"] = ("success", f"Configuración «{upload.name}» cargada; revise los avisos de validación.")


def cb_scope_from_url() -> None:
    url = st.session_state.get(wkey("target_url")) or ""
    fresh = default_config_dict(url)
    st.session_state[wkey("scope.allowed_domains")] = ", ".join(fresh["scope"]["allowed_domains"])
    st.session_state[wkey("scope.allowed_path_prefixes")] = ", ".join(fresh["scope"]["allowed_path_prefixes"])
    st.session_state[wkey("scope.allowed_schemes")] = fresh["scope"]["allowed_schemes"]
    st.session_state[wkey("scope.allow_private_network")] = fresh["scope"]["allow_private_network"]
    st.session_state[wkey("authorization.environment")] = fresh["authorization"]["environment"]
    st.session_state[wkey("limits.delay_seconds")] = float(max(st.session_state.get(wkey("limits.delay_seconds"), 0) or 0,
                                                               fresh["limits"]["delay_seconds"]))


def cb_apply_suggestion() -> None:
    suggestion = st.session_state.get("suggestion")
    if not suggestion:
        return
    for key in ("record_selector", "table_selector", "records_path", "file_format"):
        st.session_state[wkey(f"extraction.{key}")] = suggestion.get(key) or (None if key == "file_format" else "")
    st.session_state[wkey("extraction.method")] = suggestion["method"]
    pagination = suggestion.get("pagination") or {"mode": "none"}
    st.session_state[wkey("extraction.pagination.mode")] = pagination["mode"]
    for key in ("next_selector", "url_template", "next_field"):
        st.session_state[wkey(f"extraction.pagination.{key}")] = pagination.get(key) or ""
    st.session_state["fields_rows"] = fields_to_rows(suggestion["fields"])
    st.session_state["fields_version"] = st.session_state.get("fields_version", 0) + 1
    st.session_state["flash"] = ("success", "Reglas sugeridas aplicadas en «Campos y reglas». Revíselas antes de usarlas.")


def cb_use_method(method: str) -> None:
    st.session_state[wkey("extraction.method")] = method


def cb_start_job(cfg: ProjectConfig) -> None:
    current: ExtractionJob | None = st.session_state.get("job")
    if current and current.running:
        return
    st.session_state["job"] = ExtractionJob(cfg).start()
    st.session_state["run_confirm"] = False


def cb_reset() -> None:
    for key in list(st.session_state.keys()):
        if key != "start_url":
            del st.session_state[key]


# --------------------------------------------------------------------------------- vistas
def render_sidebar(data: dict, cfg: ProjectConfig | None, errors: list[str]) -> None:
    with st.sidebar:
        st.markdown("### Proyecto final_TAD")
        st.caption("Diagnóstico y extracción web responsable")
        st.divider()
        st.markdown("**Cargar un escenario de prueba**")
        st.selectbox("Ejemplo", list(example_catalog()), index=None, key="example_choice",
                     placeholder="Elija un ejemplo…", label_visibility="collapsed")
        st.button("Cargar ejemplo", on_click=cb_load_example, width="stretch")
        st.file_uploader("…o subir una configuración YAML", type=["yaml", "yml", "json"], key="config_upload",
                         on_change=cb_upload_config)
        st.divider()
        if st.toggle("Sitio de pruebas local", key="fixtures_on",
                     help="Sirve los fixtures ficticios en el puerto 8765 para practicar sin sitios reales."):
            st.caption(fixture_server()[1])
        st.divider()
        if st.session_state.get("started"):
            st.download_button("Descargar configuración YAML", exportable_yaml(data),
                               file_name=f"{data['project']['name'] or 'config'}.yaml", mime="text/yaml",
                               width="stretch", disabled=cfg is None,
                               help=None if cfg else "Corrija los errores de validación primero")
            st.button("Empezar de nuevo", on_click=cb_reset, width="stretch", type="tertiary")
        st.caption("Solo para sitios con autorización. Ante CAPTCHA, bloqueos o límites, la herramienta se detiene.")


def render_welcome() -> None:
    st.title("Proyecto final_TAD")
    st.markdown("Herramienta para **diagnosticar** cómo un sitio entrega su información y **extraer** datos "
                "solo dentro de un alcance autorizado, con límites, calidad y trazabilidad.")
    with st.container(border=True):
        st.markdown("#### Empezar con una URL")
        cols = st.columns([4, 1], vertical_alignment="bottom")
        cols[0].text_input("URL del sitio", key="start_url", placeholder="https://datos.ejemplo.org/catalogo")
        cols[1].button("Comenzar", type="primary", on_click=cb_new_from_url, width="stretch")
        st.caption("Se crea una configuración conservadora: sin autorización confirmada, alcance limitado al "
                   "dominio de la URL y método automático. No se hace ninguna solicitud hasta que usted lo pida.")
    cols = st.columns(3)
    for col, (title, text) in zip(cols, [
        ("1. Autorizar", "Declare quién permite el acceso, para qué y con qué límites."),
        ("2. Diagnosticar", "Pocas solicitudes para ver si el contenido es HTML, JavaScript, archivo o API."),
        ("3. Extraer y revisar", "Vista previa, confirmación, extracción con límites y descarga de resultados."),
    ]):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)
    st.info("¿Primera vez? Active **Sitio de pruebas local** en la barra lateral y cargue un ejemplo.", icon="💡")


def status_header(data: dict, cfg: ProjectConfig | None, errors: list[str]) -> list[str]:
    missing = missing_for_extraction(cfg) if cfg else []
    st.markdown(f"## {data['project']['name'] or 'Proyecto sin nombre'}")
    st.caption(data.get("target_url") or "")
    env = data["authorization"]["environment"] or "production"
    chips = st.container(horizontal=True)
    with chips:
        st.badge(ENVIRONMENTS.get(env, env), color="blue" if env == "fixture" else "violet")
        if errors:
            st.badge(f"Configuración: {len(errors)} error(es)", color="red", icon=":material/error:")
        else:
            st.badge("Configuración válida", color="green", icon=":material/check:")
        if cfg and not missing:
            st.badge("Autorización completa", color="green", icon=":material/verified_user:")
        elif cfg:
            st.badge(f"Autorización: faltan {len(missing)}", color="orange", icon=":material/lock:")
        st.badge(METHODS.get(data["extraction"]["method"] or "auto", "auto"), color="gray")
        if st.session_state.get("diagnosis"):
            st.badge("Diagnóstico hecho", color="green")
        result = current_result()
        if result:
            st.badge(f"Última ejecución: {result.status}", color="green" if result.status.startswith("completado") else "orange")
    flash = st.session_state.pop("flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])
    return missing


def tab_project(data: dict, cfg: ProjectConfig | None, errors: list[str], missing: list[str]) -> None:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("#### Sitio y proyecto")
        st.text_input("URL objetivo", key=wkey("target_url"),
                      help="Solo http(s). Cada solicitud, enlace y redirección se valida contra el alcance.")
        st.button("Ajustar alcance a esta URL", on_click=cb_scope_from_url, type="secondary",
                  help="Recalcula dominio, ruta, protocolo, entorno y pausa mínima a partir de la URL.")
        c1, c2 = st.columns(2)
        c1.text_input("Identificador del proyecto", key=wkey("project.name"), help="Minúsculas, números, - y _")
        c2.selectbox("Entorno", list(ENVIRONMENTS), format_func=ENVIRONMENTS.get, key=wkey("authorization.environment"))
        st.text_input("Descripción", key=wkey("project.description"))
        st.text_input("User-Agent declarado", key=wkey("user_agent"),
                      help="Identifíquese de forma honesta, idealmente con un contacto.")
    with right:
        st.markdown("#### Autorización")
        st.text_input("¿Quién autoriza?", key=wkey("authorization.authorized_by"),
                      placeholder="Nombre, cargo y organización propietaria")
        st.text_area("Finalidad del uso de los datos", key=wkey("authorization.purpose"), height=80)
        st.text_input("Referencia del permiso", key=wkey("authorization.evidence_reference"),
                      placeholder="Correo, contrato o ticket")
        st.date_input("Vigencia (opcional)", key=wkey("authorization.valid_until"), format="YYYY-MM-DD")
        st.checkbox("Revisé términos de uso, licencia y políticas del sitio", key=wkey("authorization.terms_reviewed"))
        st.checkbox("El permiso incluye acceso con cuenta (autenticación)", key=wkey("authorization.allow_authentication"))
        st.checkbox("**Confirmo** que tengo autorización para este alcance y finalidad", key=wkey("authorization.confirmed"))
    st.divider()
    render_checklist(cfg, errors, missing)


def render_checklist(cfg: ProjectConfig | None, errors: list[str], missing: list[str]) -> None:
    if errors:
        with st.container(border=True):
            st.markdown("**La configuración tiene errores** — no se puede hacer ninguna solicitud:")
            for message in errors:
                st.markdown(f"- `{message.split(':', 1)[0]}`: {message.split(':', 1)[-1].strip()}")
        return
    assert cfg is not None
    diag_missing = missing_for_diagnosis(cfg)
    if not missing:
        st.success("Autorización declarada completa: puede previsualizar y extraer tras confirmar cada ejecución.",
                   icon=":material/verified_user:")
        return
    mode = "solo validación" if diag_missing else "solo diagnóstico pasivo y pruebas con archivos locales"
    with st.container(border=True):
        st.markdown(f"**Modo actual: {mode}.** Para extraer falta:")
        for item in missing:
            st.markdown(f"- {item}")


def tab_scope(data: dict, errors: list[str]) -> None:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("#### Alcance autorizado")
        st.text_input("Dominios permitidos (separados por coma)", key=wkey("scope.allowed_domains"),
                      help="Exactos; use *.dominio.org para incluir subdominios. 'www.' es un dominio distinto.")
        st.text_input("Prefijos de ruta permitidos", key=wkey("scope.allowed_path_prefixes"), help="Cada uno empieza por /")
        st.multiselect("Protocolos", ["https", "http"], key=wkey("scope.allowed_schemes"))
        st.checkbox("Respetar robots.txt", key=wkey("scope.respect_robots_txt"),
                    help="Recomendado siempre. Desactivarlo solo si el propietario lo indica por escrito.")
        st.checkbox("Permitir red local (solo fixtures)", key=wkey("scope.allow_private_network"))
        st.multiselect("Formatos de salida", ["csv", "json", "sqlite"], key=wkey("output.formats"))
        if not st.session_state.get(wkey("scope.respect_robots_txt"), True):
            st.warning("Ha desactivado robots.txt. Documente la autorización expresa del propietario.")
    with c2:
        st.markdown("#### Límites")
        a, b = st.columns(2)
        a.number_input("Páginas máx.", 1, 100, key=wkey("limits.max_pages"))
        b.number_input("Registros máx.", 1, 10_000, key=wkey("limits.max_records"))
        a.number_input("Solicitudes máx.", 1, 500, key=wkey("limits.max_requests"))
        b.number_input("Tiempo máx. (s)", 1.0, 3600.0, key=wkey("limits.max_seconds"), step=10.0)
        a.number_input("Pausa entre solicitudes (s)", 0.0, 60.0, key=wkey("limits.delay_seconds"), step=0.5,
                       help="Mínimo 1 s para dominios remotos.")
        b.number_input("Timeout por solicitud (s)", 1.0, 120.0, key=wkey("limits.timeout_seconds"))
        a.number_input("Reintentos (solo fallos transitorios)", 0, 3, key=wkey("limits.max_retries"))
        b.number_input("Solicitudes del diagnóstico", 1, 5, key=wkey("diagnosis.max_requests"))
        a.number_input("Clics «cargar más» máx.", 0, 50, key=wkey("limits.max_clicks"))
        b.number_input("Scrolls máx.", 0, 50, key=wkey("limits.max_scrolls"))
        st.caption("Concurrencia fija en 1. CAPTCHA, 429, 403 o login inesperado detienen la ejecución sin reintentos.")
    scope_errors = [e for e in errors if e.startswith(("scope", "limits", "target_url", "(raíz)", "diagnosis"))]
    for message in scope_errors:
        st.error(message)


def tab_diagnosis(data: dict, cfg: ProjectConfig | None) -> None:
    if cfg is None:
        st.info("Corrija la configuración para poder diagnosticar.", icon=":material/info:")
        return
    blocked = missing_for_diagnosis(cfg)
    n = cfg.diagnosis.max_requests + (1 if st.session_state.get(wkey("diagnosis.render_with_browser")) else 0)
    st.markdown(f"Inspección pasiva de **{urlsplit(cfg.target_url).netloc}**: hasta **{n} solicitudes** "
                "(robots.txt, el documento y una redirección). No se ejecutan formularios ni se prueban rutas no enlazadas.")
    st.checkbox("Comparar con render del navegador (+1 solicitud, requiere Chrome)", key=wkey("diagnosis.render_with_browser"))
    consent = True
    if cfg.authorization.environment != "fixture":
        consent = st.checkbox(f"Confirmo que tengo permiso para esta inspección de hasta {n} solicitudes", key="diag_consent")
    for item in blocked:
        st.warning(item)
    if st.button("Ejecutar diagnóstico", type="primary", disabled=bool(blocked) or not consent):
        with st.spinner("Inspeccionando con límites conservadores…"):
            try:
                diagnosis = ExtractionEngine(cfg).diagnose()
            except (AuthorizationError, WebExtractorError) as exc:
                st.error(str(exc))
                return
        st.session_state["diagnosis"] = diagnosis
        st.session_state["suggestion"] = suggest_extraction(diagnosis) if not diagnosis.stopped else None
    diagnosis = st.session_state.get("diagnosis")
    if diagnosis is None:
        return
    st.divider()
    m = st.columns(4)
    m[0].metric("Estado HTTP", diagnosis.status_code if diagnosis.status_code is not None else "—")
    m[1].metric("Tipo", (diagnosis.content_type or "—").split(";")[0])
    m[2].metric("Solicitudes usadas", diagnosis.requests_used)
    m[3].metric("Indicios", len(diagnosis.findings))
    for incident in diagnosis.incidents:
        st.error(f"**Parada: {incident.kind}** — {incident.message}\n\n**Siguiente paso legítimo:** {incident.next_step}",
                 icon=":material/block:")
    if diagnosis.recommendations:
        st.markdown("#### Métodos sugeridos")
        cols = st.columns(len(diagnosis.recommendations))
        for col, rec in zip(cols, diagnosis.recommendations):
            with col.container(border=True, height="stretch"):
                st.markdown(f"**{METHODS.get(rec.method, rec.method)}**")
                st.progress(rec.score, text=f"{rec.score:.2f}")
                st.badge(f"Confianza {rec.confidence}", color=CONFIDENCE_COLOR[rec.confidence])
                if not rec.executable:
                    st.badge("No verificado / no ejecutar", color="red")
                for reason in rec.reasons[:4]:
                    st.caption(f"✓ {reason}")
                for reason in rec.against[:3]:
                    st.caption(f"✗ {reason}")
                for req in rec.requirements:
                    st.caption(f"• {req}")
                if rec.executable:
                    st.button("Usar este método", key=f"use_{rec.method}", on_click=cb_use_method, args=(rec.method,))
    if st.session_state.get("suggestion"):
        s = st.session_state["suggestion"]
        with st.container(border=True):
            st.markdown(f"**Reglas sugeridas** ({len(s['fields'])} campos, método {s['method']}). Son un borrador: "
                        "revise selectores y tipos.")
            st.button("Aplicar sugerencia a «Campos y reglas»", on_click=cb_apply_suggestion)
    if diagnosis.findings:
        st.markdown("#### Indicios observados (heurísticos)")
        st.dataframe(pd.DataFrame([{"Categoría": f.category, "Indicio": f.message, "Evidencia": f.evidence[:200]}
                                   for f in diagnosis.findings]), hide_index=True, width="stretch")
    with st.expander("Limitaciones del diagnóstico"):
        for item in diagnosis.limitations:
            st.markdown(f"- {item}")
    st.download_button("Descargar informe de diagnóstico (Markdown)", diagnosis_markdown(diagnosis),
                       file_name="diagnostico.md", mime="text/markdown")


def tab_fields(data: dict, errors: list[str]) -> None:
    method = st.session_state.get(wkey("extraction.method")) or "auto"
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        st.selectbox("Método de adquisición", list(METHODS), format_func=METHODS.get, key=wkey("extraction.method"))
        if method in ("static_html", "browser", "auto"):
            st.text_input("Selector de registro (CSS)", key=wkey("extraction.record_selector"),
                          placeholder="article.producto", help="Un elemento por registro.")
            st.text_input("…o selector de tabla", key=wkey("extraction.table_selector"), placeholder="table#datos",
                          help="Con tabla, cada campo usa «column» (encabezado).")
        if method in ("api", "structured_file", "auto"):
            st.text_input("Ruta a la lista de registros (JSON)", key=wkey("extraction.records_path"), placeholder="data.items")
        if method == "structured_file":
            st.selectbox("Formato del archivo", [None, "csv", "json"], key=wkey("extraction.file_format"),
                         format_func=lambda v: "—" if v is None else v.upper())
        modes = {"static_html": ["none", "next_link", "url_template"], "browser": ["none", "next_link"],
                 "api": ["none", "next_field", "page_param"]}.get(method, ["none"])
        if st.session_state.get(wkey("extraction.pagination.mode")) not in modes:
            st.session_state[wkey("extraction.pagination.mode")] = "none"
        st.selectbox("Paginación", modes, key=wkey("extraction.pagination.mode"), format_func={
            "none": "Sin paginación", "next_link": "Enlace «siguiente»", "url_template": "Plantilla de URL con {page}",
            "next_field": "Campo «next» en la respuesta", "page_param": "Parámetro de página"}.get)
        mode = st.session_state.get(wkey("extraction.pagination.mode"))
        if mode == "next_link":
            st.text_input("Selector del enlace siguiente", key=wkey("extraction.pagination.next_selector"), placeholder="a[rel=next]")
        elif mode == "url_template":
            st.text_input("Plantilla de URL", key=wkey("extraction.pagination.url_template"))
        elif mode == "next_field":
            st.text_input("Ruta del campo next", key=wkey("extraction.pagination.next_field"), placeholder="links.next")
        elif mode == "page_param":
            st.text_input("Parámetro", key=wkey("extraction.pagination.page_param"))
        if method == "browser":
            with st.expander("Opciones del navegador", expanded=True):
                st.text_input("Esperar al selector", key=wkey("extraction.browser.wait_selector"))
                st.text_input("Botón «cargar más»", key=wkey("extraction.browser.load_more_selector"), placeholder="#load-more")
                st.checkbox("Scroll infinito", key=wkey("extraction.browser.infinite_scroll"))
                st.number_input("Espera máx. (s)", 1.0, 60.0, key=wkey("extraction.browser.wait_timeout_seconds"))
        if method == "api":
            with st.expander("API documentada", expanded=True):
                st.checkbox("Es pública y está documentada por el propietario", key=wkey("extraction.api.documented"))
                st.text_input("URL de la documentación", key=wkey("extraction.api.documentation_url"))
        with st.expander("Autenticación autorizada"):
            st.selectbox("Tipo", ["none", "form", "header"], key=wkey("auth.type"),
                         format_func={"none": "Sin autenticación", "form": "Formulario (credenciales propias)",
                                      "header": "Token/API key documentado (encabezado)"}.get)
            if st.session_state.get(wkey("auth.type")) == "form":
                st.text_input("URL de acceso", key=wkey("auth.login_url"))
                st.text_input("Campo de usuario", key=wkey("auth.username_field"))
                st.text_input("Campo de contraseña", key=wkey("auth.password_field"))
                st.text_input("Variable de entorno del usuario", key=wkey("auth.username_env"))
                st.text_input("Variable de entorno de la contraseña", key=wkey("auth.password_env"))
                for env_key in ("auth.username_env", "auth.password_env"):
                    name = st.session_state.get(wkey(env_key))
                    if name:
                        defined = bool(os.environ.get(name))
                        st.caption(f"{'✓' if defined else '✗'} `{name}` {'definida' if defined else 'no definida en este proceso'}")
            elif st.session_state.get(wkey("auth.type")) == "header":
                st.caption("Solo para APIs o archivos cuya documentación indique el encabezado y emita el token.")
                st.text_input("Encabezado", key=wkey("auth.header_name"))
                st.text_input("Prefijo del valor", key=wkey("auth.header_prefix"), help="Ej.: «Bearer » o vacío")
                st.text_input("Variable de entorno del token", key=wkey("auth.token_env"), placeholder="MI_API_TOKEN")
                name = st.session_state.get(wkey("auth.token_env"))
                if name:
                    defined = bool(os.environ.get(name))
                    st.caption(f"{'✓' if defined else '✗'} `{name}` {'definida' if defined else 'no definida en este proceso'}")
            if st.session_state.get(wkey("auth.type")) != "none":
                st.caption("Las credenciales nunca se escriben aquí: solo el nombre de la variable de entorno.")
    with c2:
        st.markdown("#### Campos")
        st.caption("Selector CSS relativo al registro, «column» para tablas o «path» para JSON/CSV. "
                   "El orden de limpieza es: normalizar → patrón → tipo → validar.")
        frame = pd.DataFrame(st.session_state.get("fields_rows") or [], columns=FIELD_COLUMNS)
        edited = st.data_editor(
            frame, key=f"fields_editor_{st.session_state.get('fields_version', 0)}", num_rows="dynamic",
            hide_index=True, width="stretch",
            column_config={
                "name": st.column_config.TextColumn("Campo", required=True),
                "selector": st.column_config.TextColumn("Selector CSS"),
                "attribute": st.column_config.TextColumn("Atributo", help="text, html, href, src, data-…"),
                "column": st.column_config.TextColumn("Columna (tabla)"),
                "path": st.column_config.TextColumn("Ruta (JSON/CSV)"),
                "type": st.column_config.SelectboxColumn("Tipo", options=list(SUPPORTED_TYPES), required=True),
                "required": st.column_config.CheckboxColumn("Obligatorio"),
                "normalize": st.column_config.MultiselectColumn("Normalizar", options=sorted(NORMALIZERS)),
                "pattern": st.column_config.TextColumn("Patrón (regex)"),
                "date_format": st.column_config.TextColumn("Formato fecha"),
                "regex": st.column_config.TextColumn("Validar regex"),
                "min": st.column_config.NumberColumn("Mín."),
                "max": st.column_config.NumberColumn("Máx."),
                "choices": st.column_config.TextColumn("Valores permitidos", help="Separados por coma"),
            })
        st.session_state["fields_current"] = edited
        names = [n for n in edited["name"].dropna().astype(str) if n.strip()] if "name" in edited else []
        current = [d for d in st.session_state.get(wkey("extraction.deduplicate_on"), []) if d in names]
        st.session_state[wkey("extraction.deduplicate_on")] = current
        st.multiselect("Deduplicar por", names, key=wkey("extraction.deduplicate_on"),
                       placeholder="Todos los campos", help="Vacío = todos los campos.")
        a, b = st.columns(2)
        a.checkbox("Conservar valor original (raw)", key=wkey("extraction.keep_raw"))
        b.checkbox("Descartar registros inválidos", key=wkey("extraction.drop_invalid"))
    field_errors = [e for e in errors if e.startswith(("extraction", "auth"))]
    for message in field_errors:
        st.error(message)


def show_records(records, quality) -> None:
    if not records:
        st.warning("Sin registros con las reglas actuales. Revise el selector de registro y los selectores de campos; "
                   "si el contenido se genera con JavaScript, pruebe el método Navegador.")
        return
    rows = []
    for r in records:
        row = {"estado": r.lineage["validation_status"], **r.data}
        row["errores"] = "; ".join(r.lineage["validation_errors"])
        rows.append(row)
    frame = pd.DataFrame(rows, dtype=object).fillna("—").astype(str)
    st.dataframe(frame, hide_index=True, width="stretch", column_config={
        "estado": st.column_config.TextColumn("Estado", width="small")})
    m = st.columns(4)
    m[0].metric("Válidos", quality.valid)
    m[1].metric("Advertencias", quality.with_warnings)
    m[2].metric("Inválidos", quality.invalid)
    m[3].metric("Duplicados", quality.duplicates_removed)


def tab_preview(cfg: ProjectConfig | None) -> None:
    if cfg is None:
        st.info("Corrija la configuración para ver la vista previa.", icon=":material/info:")
        return
    c1, c2 = st.columns(2, gap="large")
    with c1.container(border=True):
        st.markdown("**Probar con un archivo local** (0 solicitudes)")
        st.caption("Guarde una página permitida (HTML, JSON o CSV) y pruebe sus reglas sin tocar el sitio.")
        upload = st.file_uploader("Archivo", type=["html", "htm", "json", "csv"], key="preview_file",
                                  label_visibility="collapsed")
        if st.button("Vista previa del archivo", disabled=upload is None or cfg.extraction.method == "auto"):
            target = ROOT / "outputs" / "_gui_preview" / upload.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(upload.getvalue())
            try:
                st.session_state["preview"] = ExtractionEngine(cfg).preview(max_records=20, from_file=target)
            except WebExtractorError as exc:
                st.error(str(exc))
    missing = missing_for_extraction(cfg)
    with c2.container(border=True):
        st.markdown("**Vista previa en vivo** (1 página, ≤ 2 solicitudes)")
        st.caption("Usa el adaptador real con clics y scrolls desactivados.")
        consent = True
        if cfg.authorization.environment != "fixture" and not missing:
            consent = st.checkbox("Confirmo estas solicitudes al sitio", key="preview_consent")
        if st.button("Vista previa en vivo", type="primary", disabled=bool(missing) or not consent):
            with st.spinner("Obteniendo una página…"):
                try:
                    st.session_state["preview"] = ExtractionEngine(cfg).preview(max_records=10)
                except WebExtractorError as exc:
                    st.error(str(exc))
        if missing:
            st.caption("Bloqueada hasta completar la autorización (paso 1).")
    if cfg.extraction.method == "auto":
        st.info("Elija un método explícito en «Campos y reglas» para previsualizar.")
    preview = st.session_state.get("preview")
    if preview is None:
        return
    st.markdown(f"#### Resultado — {preview.source}")
    st.caption(f"Solicitudes usadas: {preview.requests_used}")
    for incident in preview.incidents:
        st.error(f"**{incident.kind}** — {incident.message}\n\n**Siguiente paso:** {incident.next_step}")
    show_records(preview.records, preview.quality)
    for sample in preview.quality.error_samples[:10]:
        st.caption(f"• {sample}")


def current_result():
    job: ExtractionJob | None = st.session_state.get("job")
    if job and not job.running and job.result:
        return job.result
    return st.session_state.get("last_result")


def tab_run(cfg: ProjectConfig | None) -> None:
    if cfg is None:
        st.info("Corrija la configuración para extraer.", icon=":material/info:")
        return
    missing = missing_for_extraction(cfg)
    job: ExtractionJob | None = st.session_state.get("job")
    lim = cfg.limits
    st.markdown(f"Extraer de **{cfg.target_url}** con el método **{METHODS[cfg.extraction.method]}**.")
    m = st.columns(5)
    m[0].metric("Solicitudes", lim.max_requests)
    m[1].metric("Páginas", lim.max_pages)
    m[2].metric("Registros", lim.max_records)
    m[3].metric("Tiempo", f"{lim.max_seconds:.0f} s")
    m[4].metric("Pausa", f"{lim.delay_seconds} s")
    if missing:
        st.warning("La extracción está bloqueada. Complete la autorización en el paso 1:\n\n- " + "\n- ".join(missing),
                   icon=":material/lock:")
        return
    running = bool(job and job.running)
    confirm = st.checkbox(f"Confirmo la extracción con estos límites (hasta {lim.max_requests} solicitudes).",
                          key="run_confirm", disabled=running)
    st.button("Iniciar extracción", type="primary", disabled=running or not confirm, on_click=cb_start_job, args=(cfg,))
    if job:
        job_panel()


@st.fragment(run_every=1.0)
def job_panel() -> None:
    job: ExtractionJob | None = st.session_state.get("job")
    if job is None:
        return
    counters = job.counters()
    with st.container(border=True):
        top = st.columns([3, 1], vertical_alignment="center")
        if job.running:
            top[0].markdown(f"**Extrayendo…** {job.elapsed:.0f} s")
            top[1].button("Cancelar", on_click=job.request_cancel, type="secondary", width="stretch")
        else:
            top[0].markdown(f"**Ejecución terminada** en {job.elapsed:.1f} s")
        c = st.columns(5)
        for col, (label, key) in zip(c, [("Solicitudes", "solicitudes"), ("Páginas", "paginas"),
                                          ("Registros", "registros"), ("Clics", "clics"), ("Scrolls", "scrolls")]):
            col.metric(label, counters[key])
        entries = job.snapshot()[-12:]
        if entries:
            st.dataframe(pd.DataFrame([{"Hora (UTC)": e.timestamp[11:19], "Acción": e.action, "Destino": e.target,
                                        "Detalle": e.detail, "Resultado": e.outcome} for e in entries]),
                         hide_index=True, width="stretch")
    if job.error:
        st.error(job.error)
    if not job.running and not st.session_state.get("job_reported") is job:
        st.session_state["job_reported"] = job
        if job.result:
            st.session_state["last_result"] = job.result
        st.rerun(scope="app")


def tab_results(cfg: ProjectConfig | None) -> None:
    result = current_result()
    if result is None:
        st.info("Aún no hay resultados en esta sesión.", icon=":material/inbox:")
        render_history(cfg)
        return
    style = STATUS_STYLE.get(result.status, "info")
    getattr(st, style)(f"**{result.status}** — {STATUS_TEXT.get(result.status, '')}\n\n{result.status_message}")
    if result.requires_human_review:
        st.warning("**Revisión humana requerida:** la estructura cambió frente al perfil anterior. No se actualizó "
                   "la línea base ni se corrigió nada automáticamente.", icon=":material/rule:")
    b, q = result.budget, result.quality
    m = st.columns(5)
    m[0].metric("Exportados", q.exported)
    m[1].metric("Válidos", q.valid)
    m[2].metric("Advertencias", q.with_warnings)
    m[3].metric("Inválidos", q.invalid)
    m[4].metric("Solicitudes", f"{b.get('requests')}/{b.get('max_requests')}")
    data_tab, quality_tab, incidents_tab, files_tab = st.tabs(["Datos", "Calidad", "Incidencias y cambios", "Archivos"], key="result_tabs")
    with data_tab:
        show_records(result.records, q)
    with quality_tab:
        st.dataframe(pd.DataFrame([{"Campo": name, "Con valor": fq.filled, "Vacíos": fq.empty, "Errores": fq.invalid,
                                    "Llenado": fq.fill_rate(q.total_raw)} for name, fq in q.fields.items()]),
                     hide_index=True, width="stretch",
                     column_config={"Llenado": st.column_config.ProgressColumn("Llenado", min_value=0, max_value=1, format="percent")})
        for sample in q.error_samples[:15]:
            st.caption(f"• {sample}")
    with incidents_tab:
        if not result.incidents and not result.profile_changes:
            st.success("Sin incidencias ni cambios de estructura.")
        for i in result.incidents:
            st.markdown(f"- **{i.kind}** ({i.severity}): {i.message}  \n  _Siguiente paso:_ {i.next_step}")
        for c in result.profile_changes:
            st.markdown(f"- Cambio **{c['severity']}** · {c['kind']}: {c['message']}")
        st.markdown("**Siguientes pasos**")
        for step in result.next_steps:
            st.markdown(f"- {step}")
    with files_tab:
        cols = st.columns(3)
        downloads = [("csv", "Datos CSV", "text/csv"), ("json", "Datos JSON", "application/json"),
                     ("report", "Informe (Markdown)", "text/markdown"), ("summary", "Resumen JSON", "application/json"),
                     ("actions", "Acciones (JSONL)", "application/json"), ("log", "Log sin secretos", "text/plain"),
                     ("config", "Configuración efectiva", "application/json")]
        for i, (key, label, mime) in enumerate(downloads):
            path = result.outputs.get(key)
            if path and Path(path).exists():
                cols[i % 3].download_button(label, Path(path).read_bytes(), file_name=Path(path).name, mime=mime,
                                            width="stretch", key=f"dl_{key}")
        if result.outputs.get("sqlite"):
            st.caption(f"Base SQLite acumulativa: `{result.outputs['sqlite']}`")
        st.caption(f"Carpeta de la ejecución: `{result.run_dir}`")
        st.caption(f"Huella SHA-256 de la configuración: `{result.config_sha256}` · herramienta {result.tool_version}")
    render_history(cfg)


def render_history(cfg: ProjectConfig | None) -> None:
    if cfg is None:
        return
    run_dirs = sorted((ROOT / "outputs" / cfg.project.name).glob("*/summary.json"), reverse=True)[:10]
    if not run_dirs:
        return
    rows = []
    for path in run_dirs:
        summary = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"Ejecución": summary["run_id"], "Estado": summary["status"],
                     "Exportados": summary["quality"]["exported"], "Solicitudes": summary["budget"].get("requests"),
                     "Revisión": "sí" if summary.get("requires_human_review") else "no"})
    with st.expander(f"Historial del proyecto ({len(rows)})"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def main() -> None:
    st.set_page_config(page_title="Proyecto final_TAD", page_icon=":material/travel_explore:", layout="wide")
    st.html("""<style>
      .block-container {padding-top: 2rem; max-width: 1400px;}
      [data-testid="stMetricValue"] {font-size: 1.6rem;}
      div[data-testid="stTabs"] button p {font-size: 0.95rem; font-weight: 600;}
    </style>""")
    if not st.session_state.get("started"):
        render_sidebar(collect_safe(), None, [])
        render_welcome()
        return
    data = collect()
    cfg, errors = validate(data)
    render_sidebar(data, cfg, errors)
    missing = status_header(data, cfg, errors)
    tabs = st.tabs(["1 · Proyecto y autorización", "2 · Alcance y límites", "3 · Diagnóstico",
                    "4 · Campos y reglas", "5 · Vista previa", "6 · Extracción", "7 · Resultados"], key="main_tabs")
    with tabs[0]:
        tab_project(data, cfg, errors, missing)
    with tabs[1]:
        tab_scope(data, errors)
    with tabs[2]:
        tab_diagnosis(data, cfg)
    with tabs[3]:
        tab_fields(data, errors)
    with tabs[4]:
        tab_preview(cfg)
    with tabs[5]:
        tab_run(cfg)
    with tabs[6]:
        tab_results(cfg)


def collect_safe() -> dict:
    return copy.deepcopy(DEFAULTS)


if __name__ == "__main__":
    main()
