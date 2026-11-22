"""Interfaz gráfica local del extractor (Streamlit).

Ejecutar con ``python -m web_extractor gui``. Cuatro pasos: sitio y autorización → diagnóstico,
campos y vista previa → extracción → resultados. Las opciones técnicas quedan en secciones
«avanzadas». Todas las acciones que generan solicitudes pasan por las mismas puertas de
autorización del motor.
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
        st.session_state["flash"] = ("success", "Configuración inicial creada. Complete la autorización antes de "
                                                "cualquier solicitud al sitio.")


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
    url = (st.session_state.get(wkey("target_url")) or "").strip()
    if not url:
        return
    if "://" not in url:
        url = "https://" + url
        st.session_state[wkey("target_url")] = url
    fresh = default_config_dict(url)
    st.session_state[wkey("project.name")] = fresh["project"]["name"]
    st.session_state[wkey("scope.allowed_domains")] = ", ".join(fresh["scope"]["allowed_domains"])
    st.session_state[wkey("scope.allowed_path_prefixes")] = ", ".join(fresh["scope"]["allowed_path_prefixes"])
    st.session_state[wkey("scope.allowed_schemes")] = fresh["scope"]["allowed_schemes"]
    st.session_state[wkey("scope.allow_private_network")] = fresh["scope"]["allow_private_network"]
    st.session_state[wkey("authorization.environment")] = fresh["authorization"]["environment"]
    st.session_state[wkey("limits.delay_seconds")] = float(max(st.session_state.get(wkey("limits.delay_seconds"), 0) or 0,
                                                               fresh["limits"]["delay_seconds"]))
    for key in ("diagnosis", "preview", "suggestion"):
        st.session_state.pop(key, None)


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
                                                "Revíselos abajo y pulse «Vista previa en vivo».")
    elif suggestion:
        st.session_state["flash"] = ("success", "Diagnóstico listo. Se conservaron los campos que ya tenía; si prefiere "
                                                "los sugeridos, use «Reemplazar por los campos sugeridos».")


def cb_apply_suggestion() -> None:
    if st.session_state.get("suggestion"):
        apply_suggestion(st.session_state["suggestion"])
        st.session_state["flash"] = ("success", "Campos sugeridos aplicados. Revíselos antes de la vista previa.")


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
        catalog = example_catalog()
        if catalog:
            st.markdown("**Sitios ya configurados** (opcional)")
            st.selectbox("Ejemplo", list(catalog), index=None, key="example_choice",
                         placeholder="Elija un sitio…", label_visibility="collapsed")
            st.button("Cargar", on_click=cb_load_example, width="stretch")
        st.file_uploader("…o abrir una configuración guardada (YAML)", type=["yaml", "yml", "json"],
                         key="config_upload", on_change=cb_upload_config)
        if st.session_state.get("started"):
            st.divider()
            st.download_button("Guardar configuración (YAML)", exportable_yaml(data),
                               file_name=f"{data['project']['name'] or 'config'}.yaml", mime="text/yaml",
                               width="stretch", disabled=cfg is None,
                               help=None if cfg else "Corrija los errores de validación primero")
            st.button("Empezar de nuevo", on_click=cb_reset, width="stretch", type="tertiary")
        st.caption("Solo para sitios con autorización. Ante CAPTCHA, bloqueos o límites, la herramienta se detiene.")


def render_welcome() -> None:
    st.title("Proyecto final_TAD")
    st.markdown("Diagnostica cómo un sitio entrega su información y **extrae** datos solo dentro de un alcance "
                "autorizado, con límites, calidad y trazabilidad. Funciona con cualquier URL.")
    with st.container(border=True):
        st.markdown("#### ¿De qué sitio quiere obtener datos?")
        cols = st.columns([4, 1], vertical_alignment="bottom")
        cols[0].text_input("URL del sitio", key="start_url", placeholder="https://www.datos.gob.mx/dataset/")
        cols[1].button("Comenzar", type="primary", on_click=cb_new_from_url, width="stretch")
        st.caption("No se hace ninguna solicitud al sitio hasta que usted complete la autorización y lo pida.")
    cols = st.columns(4)
    for col, (title, text) in zip(cols, STEPS):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(text)


STEPS = [
    ("1 · Sitio y autorización", "Quién permite el acceso y para qué."),
    ("2 · Diagnóstico y campos", "Cómo entrega los datos el sitio, qué campos tomar y vista previa."),
    ("3 · Extraer", "Extracción con límites; se puede cancelar."),
    ("4 · Resultados", "Calidad, incidencias y descargas (CSV, Excel, JSON)."),
]


def status_header(data: dict, cfg: ProjectConfig | None, errors: list[str]) -> list[str]:
    missing = missing_for_extraction(cfg) if cfg else []
    st.markdown(f"## {urlsplit(data.get('target_url') or '').netloc or 'Proyecto'}")
    st.caption(data.get("target_url") or "")
    chips = st.container(horizontal=True)
    with chips:
        if errors:
            st.badge(f"Configuración: {len(errors)} error(es)", color="red", icon=":material/error:")
        if cfg and not missing:
            st.badge("1 · Autorización completa", color="green", icon=":material/verified_user:")
        elif cfg:
            st.badge(f"1 · Autorización: faltan {len(missing)}", color="orange", icon=":material/lock:")
        diagnosis = st.session_state.get("diagnosis")
        if diagnosis is not None:
            st.badge("2 · Diagnóstico detenido" if diagnosis.stopped else "2 · Diagnóstico hecho",
                     color="red" if diagnosis.stopped else "green")
        if st.session_state.get("preview") is not None:
            st.badge("2 · Vista previa hecha", color="green")
        result = current_result()
        if result:
            st.badge(f"4 · Última ejecución: {result.status}",
                     color="green" if result.status.startswith("completado") else "orange")
    flash = st.session_state.pop("flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])
    return missing


def step_site(data: dict, cfg: ProjectConfig | None, errors: list[str], missing: list[str]) -> None:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("#### Sitio")
        st.text_input("URL", key=wkey("target_url"), on_change=cb_scope_from_url,
                      help="Solo http(s). El alcance (dominio y ruta) se ajusta solo a esta URL.")
        st.markdown("#### Autorización")
        st.text_input("¿Quién autoriza?", key=wkey("authorization.authorized_by"),
                      placeholder="Propietario del sitio, o la licencia de datos abiertos que permite el uso")
        st.text_area("Finalidad del uso de los datos", key=wkey("authorization.purpose"), height=80)
        st.text_input("Referencia del permiso", key=wkey("authorization.evidence_reference"),
                      placeholder="Enlace a la licencia o términos, correo, contrato…")
        st.checkbox("Revisé términos de uso, licencia y políticas del sitio", key=wkey("authorization.terms_reviewed"))
        st.checkbox("**Confirmo** que tengo autorización para este alcance y finalidad", key=wkey("authorization.confirmed"))
        with st.expander("Opciones avanzadas"):
            st.text_input("Identificador del proyecto", key=wkey("project.name"), help="Minúsculas, números, - y _")
            st.text_input("Descripción", key=wkey("project.description"))
            st.text_input("User-Agent declarado", key=wkey("user_agent"),
                          help="Identifíquese de forma honesta, idealmente con un contacto.")
            st.date_input("Vigencia del permiso", key=wkey("authorization.valid_until"), format="YYYY-MM-DD")
            st.checkbox("El permiso incluye acceso con cuenta (autenticación)", key=wkey("authorization.allow_authentication"))
    with right:
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
        st.success("Autorización completa. Siga con la pestaña **2 · Diagnóstico y campos**.", icon=":material/verified_user:")
        return
    mode = "solo validación" if diag_missing else "puede diagnosticar, pero aún no extraer"
    with st.container(border=True):
        st.markdown(f"**Ahora: {mode}.** Para extraer falta:")
        for item in missing:
            st.markdown(f"- {item}")


def step_diagnosis(data: dict, cfg: ProjectConfig | None, errors: list[str]) -> None:
    if cfg is None:
        st.info("Corrija la configuración (paso 1) para poder diagnosticar.", icon=":material/info:")
        return
    blocked = missing_for_diagnosis(cfg)
    n = cfg.diagnosis.max_requests + (1 if st.session_state.get(wkey("diagnosis.render_with_browser")) else 0)
    st.markdown(f"Inspección de **{urlsplit(cfg.target_url).netloc}** con hasta **{n} solicitudes**. "
                "Detecta si los datos vienen en HTML, con JavaScript, en un archivo o en una API, y si hay barreras.")
    st.checkbox("Comparar también con el navegador (+1 solicitud, requiere Chrome o Edge)",
                key=wkey("diagnosis.render_with_browser"))
    consent = True
    if cfg.authorization.environment != "fixture":
        consent = st.checkbox(f"Confirmo que tengo permiso para esta inspección de hasta {n} solicitudes", key="diag_consent")
    for item in blocked:
        st.warning(item)
    st.button("Ejecutar diagnóstico", type="primary", disabled=bool(blocked) or not consent, on_click=cb_diagnose)
    diagnosis = st.session_state.get("diagnosis")
    if diagnosis is not None:
        show_diagnosis(diagnosis)
    st.divider()
    show_fields(errors)
    st.divider()
    show_preview(cfg)


AUTH_HINT = ("Si tiene una cuenta o un token **autorizados por el propietario**, configúrelos en «Ajustes del "
             "método (avanzado)» → Autenticación autorizada, y marque en el paso 1 que el permiso incluye "
             "autenticación. Las credenciales se leen de variables de entorno, nunca se escriben aquí.")


def show_diagnosis(diagnosis) -> None:
    for incident in diagnosis.incidents:
        st.error(f"**Parada: {incident.kind}** — {incident.message}\n\n**Siguiente paso legítimo:** {incident.next_step}",
                 icon=":material/block:")
    if any(i.kind == "auth_required" for i in diagnosis.incidents) or any(f.code == "html.login_form" for f in diagnosis.findings):
        st.info(AUTH_HINT, icon=":material/key:")
    best = diagnosis.best
    if best is not None and not diagnosis.stopped:
        with st.container(border=True):
            st.markdown(f"**Método recomendado: {METHODS.get(best.method, best.method)}**")
            st.badge(f"Confianza {best.confidence} ({best.score:.2f})", color=CONFIDENCE_COLOR[best.confidence])
            for reason in best.reasons[:3]:
                st.caption(f"✓ {reason}")
            for req in best.requirements:
                st.caption(f"• {req}")
    if diagnosis.findings:
        st.markdown("**Qué se detectó en el sitio**")
        for f in diagnosis.findings[:10]:
            st.markdown(f"- **{f.category}:** {f.message}")
    with st.expander("Ver detalle: otros métodos, evidencia y limitaciones"):
        m = st.columns(4)
        m[0].metric("Estado HTTP", diagnosis.status_code if diagnosis.status_code is not None else "—")
        m[1].metric("Tipo", (diagnosis.content_type or "—").split(";")[0])
        m[2].metric("Solicitudes usadas", diagnosis.requests_used)
        m[3].metric("Indicios", len(diagnosis.findings))
        if diagnosis.recommendations:
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
        if diagnosis.findings:
            st.dataframe(pd.DataFrame([{"Categoría": f.category, "Indicio": f.message, "Evidencia": f.evidence[:200]}
                                       for f in diagnosis.findings]), hide_index=True, width="stretch")
        for item in diagnosis.limitations:
            st.caption(f"• {item}")
        st.download_button("Descargar informe de diagnóstico (Markdown)", diagnosis_markdown(diagnosis),
                           file_name="diagnostico.md", mime="text/markdown")


BASIC_FIELD_COLUMNS = ["name", "selector", "attribute", "column", "path", "type", "required"]


def show_fields(errors: list[str]) -> None:
    method = st.session_state.get(wkey("extraction.method")) or "auto"
    st.markdown("#### Campos a extraer")
    st.caption("Tras el diagnóstico aparecen campos sugeridos. Puede renombrarlos, borrarlos o añadir filas.")
    suggestion = st.session_state.get("suggestion")
    if suggestion and fields_to_rows(suggestion["fields"]) != st.session_state.get("fields_rows"):
        st.button(f"Reemplazar por los campos sugeridos ({len(suggestion['fields'])})", on_click=cb_apply_suggestion)
    advanced = st.toggle("Mostrar columnas avanzadas (limpieza y validación)", key="fields_advanced")
    frame = pd.DataFrame(st.session_state.get("fields_rows") or [], columns=FIELD_COLUMNS)
    edited = st.data_editor(
        frame, key=f"fields_editor_{st.session_state.get('fields_version', 0)}", num_rows="dynamic",
        hide_index=True, width="stretch", column_order=None if advanced else BASIC_FIELD_COLUMNS,
        column_config={
            "name": st.column_config.TextColumn("Campo", required=True),
            "selector": st.column_config.TextColumn("Selector CSS"),
            "attribute": st.column_config.TextColumn("Atributo", help="text, html, href, src, data-…"),
            "column": st.column_config.TextColumn("Columna (tabla)"),
            "path": st.column_config.TextColumn("Ruta (JSON/XML/CSV)"),
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
    with st.expander("Ajustes del método (avanzado)"):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.selectbox("Método de adquisición", list(METHODS), format_func=METHODS.get, key=wkey("extraction.method"))
            if method in ("static_html", "browser", "auto"):
                st.text_input("Selector de registro (CSS)", key=wkey("extraction.record_selector"),
                              placeholder="article.producto", help="Un elemento por registro.")
                st.text_input("…o selector de tabla", key=wkey("extraction.table_selector"), placeholder="table#datos",
                              help="Con tabla, cada campo usa «Columna».")
            if method in ("api", "structured_file", "auto"):
                st.text_input("Ruta a la lista de registros (JSON/XML)", key=wkey("extraction.records_path"),
                              placeholder="data.items")
            if method == "structured_file":
                st.selectbox("Formato del archivo", [None, "csv", "json", "xml"], key=wkey("extraction.file_format"),
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
                st.text_input("Selector del enlace siguiente", key=wkey("extraction.pagination.next_selector"),
                              placeholder="a[rel=next]")
            elif mode == "url_template":
                st.text_input("Plantilla de URL", key=wkey("extraction.pagination.url_template"))
            elif mode == "next_field":
                st.text_input("Ruta del campo next", key=wkey("extraction.pagination.next_field"), placeholder="links.next")
            elif mode == "page_param":
                st.text_input("Parámetro", key=wkey("extraction.pagination.page_param"))
            st.multiselect("Deduplicar por", names, key=wkey("extraction.deduplicate_on"),
                           placeholder="Todos los campos", help="Vacío = todos los campos.")
            st.checkbox("Conservar valor original (raw)", key=wkey("extraction.keep_raw"))
            st.checkbox("Descartar registros inválidos", key=wkey("extraction.drop_invalid"))
        with c2:
            if method == "browser":
                st.markdown("**Navegador**")
                st.text_input("Esperar al selector", key=wkey("extraction.browser.wait_selector"))
                st.text_input("Botón «cargar más»", key=wkey("extraction.browser.load_more_selector"), placeholder="#load-more")
                st.checkbox("Scroll infinito", key=wkey("extraction.browser.infinite_scroll"))
                st.number_input("Espera máx. (s)", 1.0, 60.0, key=wkey("extraction.browser.wait_timeout_seconds"))
            if method == "api":
                st.markdown("**API documentada**")
                st.checkbox("Es pública y está documentada por el propietario", key=wkey("extraction.api.documented"))
                st.text_input("URL de la documentación", key=wkey("extraction.api.documentation_url"))
            st.markdown("**Autenticación autorizada**")
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
    for message in [e for e in errors if e.startswith(("extraction", "auth"))]:
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


def show_preview(cfg: ProjectConfig) -> None:
    st.markdown("#### Vista previa")
    missing = missing_for_extraction(cfg)
    consent = True
    if cfg.authorization.environment != "fixture" and not missing:
        consent = st.checkbox("Confirmo estas solicitudes al sitio (1 página, ≤ 2 solicitudes)", key="preview_consent")
    if st.button("Vista previa en vivo", type="primary",
                 disabled=bool(missing) or not consent or cfg.extraction.method == "auto"):
        with st.spinner("Obteniendo una página…"):
            try:
                st.session_state["preview"] = ExtractionEngine(cfg).preview(max_records=10)
            except WebExtractorError as exc:
                st.error(str(exc))
    if missing:
        st.caption("Bloqueada hasta completar la autorización (paso 1).")
    elif cfg.extraction.method == "auto":
        st.caption("Primero ejecute el diagnóstico para elegir el método.")
    with st.expander("Probar con un archivo guardado (0 solicitudes)"):
        upload = st.file_uploader("Archivo HTML, JSON, XML o CSV", type=["html", "htm", "json", "xml", "csv"],
                                  key="preview_file")
        if st.button("Vista previa del archivo", disabled=upload is None or cfg.extraction.method == "auto"):
            target = ROOT / "outputs" / "_gui_preview" / upload.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(upload.getvalue())
            try:
                st.session_state["preview"] = ExtractionEngine(cfg).preview(max_records=20, from_file=target)
            except WebExtractorError as exc:
                st.error(str(exc))
    preview = st.session_state.get("preview")
    if preview is None:
        return
    st.caption(f"Fuente: {preview.source} · solicitudes usadas: {preview.requests_used}")
    for incident in preview.incidents:
        st.error(f"**{incident.kind}** — {incident.message}\n\n**Siguiente paso:** {incident.next_step}")
    show_records(preview.records, preview.quality)
    for sample in preview.quality.error_samples[:10]:
        st.caption(f"• {sample}")
    if preview.records:
        st.success("Si los datos se ven bien, siga con **3 · Extraer**.")


def current_result():
    job: ExtractionJob | None = st.session_state.get("job")
    if job and not job.running and job.result:
        return job.result
    return st.session_state.get("last_result")


def step_run(cfg: ProjectConfig | None, errors: list[str]) -> None:
    st.markdown("#### Límites")
    a, b, c = st.columns(3)
    a.number_input("Páginas máx.", 1, 100, key=wkey("limits.max_pages"))
    b.number_input("Registros máx.", 1, 10_000, key=wkey("limits.max_records"))
    c.number_input("Pausa entre solicitudes (s)", 0.0, 60.0, key=wkey("limits.delay_seconds"), step=0.5,
                   help="Mínimo 1 s para sitios reales. Si robots.txt pide más (Crawl-delay), se respeta.")
    st.multiselect("Formatos de salida", ["csv", "json", "excel", "sqlite"], key=wkey("output.formats"),
                   help="Además se genera un informe; con «Conservar valor original» (activado por defecto) "
                        "JSON y SQLite guardan también el dato sin procesar.")
    with st.expander("Opciones avanzadas: límites y alcance"):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            x, y = st.columns(2)
            x.number_input("Solicitudes máx.", 1, 500, key=wkey("limits.max_requests"))
            y.number_input("Tiempo máx. (s)", 1.0, 3600.0, key=wkey("limits.max_seconds"), step=10.0)
            x.number_input("Timeout por solicitud (s)", 1.0, 120.0, key=wkey("limits.timeout_seconds"))
            y.number_input("Reintentos (solo fallos transitorios)", 0, 3, key=wkey("limits.max_retries"))
            x.number_input("Clics «cargar más» máx.", 0, 50, key=wkey("limits.max_clicks"))
            y.number_input("Scrolls máx.", 0, 50, key=wkey("limits.max_scrolls"))
            x.number_input("Solicitudes del diagnóstico", 1, 5, key=wkey("diagnosis.max_requests"))
            st.caption("Concurrencia fija en 1. CAPTCHA, 429, 403 o login inesperado detienen la ejecución sin reintentos.")
        with c2:
            st.text_input("Dominios permitidos (separados por coma)", key=wkey("scope.allowed_domains"),
                          help="Exactos; use *.dominio.org para incluir subdominios. 'www.' es un dominio distinto.")
            st.text_input("Prefijos de ruta permitidos", key=wkey("scope.allowed_path_prefixes"), help="Cada uno empieza por /")
            st.multiselect("Protocolos", ["https", "http"], key=wkey("scope.allowed_schemes"))
            st.checkbox("Respetar robots.txt", key=wkey("scope.respect_robots_txt"),
                        help="Recomendado siempre. Desactivarlo solo si el propietario lo indica por escrito.")
            if not st.session_state.get(wkey("scope.respect_robots_txt"), True):
                st.warning("Ha desactivado robots.txt. Documente la autorización expresa del propietario.")
    for message in [e for e in errors if e.startswith(("scope", "limits", "target_url", "(raíz)", "diagnosis", "output"))]:
        st.error(message)
    st.divider()
    if cfg is None:
        st.info("Corrija la configuración para extraer.", icon=":material/info:")
        return
    missing = missing_for_extraction(cfg)
    job: ExtractionJob | None = st.session_state.get("job")
    lim = cfg.limits
    st.markdown(f"Extraer de **{cfg.target_url}** con el método **{METHODS[cfg.extraction.method]}**: hasta "
                f"{lim.max_pages} página(s), {lim.max_records} registros y {lim.max_requests} solicitudes, "
                f"con {lim.delay_seconds} s de pausa.")
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
                     ("excel", "Datos Excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
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
    tabs = st.tabs([title for title, _ in STEPS], key="main_tabs")
    with tabs[0]:
        step_site(data, cfg, errors, missing)
    with tabs[1]:
        step_diagnosis(data, cfg, errors)
    with tabs[2]:
        step_run(cfg, errors)
    with tabs[3]:
        tab_results(cfg)


def collect_safe() -> dict:
    return copy.deepcopy(DEFAULTS)


if __name__ == "__main__":
    main()
