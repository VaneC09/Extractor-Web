"""Configuración inicial a partir de una URL cualquiera (usada por ``init`` y por la GUI).

El resultado es siempre conservador: autorización sin confirmar, alcance limitado al host de la
URL, método ``auto`` y límites bajos. Nunca habilita extracción por sí solo.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from web_extractor.core.scope import is_private_host


def slugify(text: str, fallback: str = "proyecto") -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:60]
    if len(slug) < 2:
        slug = fallback
    return slug if slug[0].isalnum() else f"p{slug}"


def default_config_dict(url: str, name: str | None = None) -> dict[str, Any]:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    local = bool(host) and is_private_host(host)
    path = parts.path or "/"
    prefix = path if path.endswith("/") else (path.rsplit("/", 1)[0] + "/" if "/" in path[1:] else "/")
    return {
        "version": 1,
        "project": {"name": slugify(name or f"{host}{path}"), "description": ""},
        "target_url": url.strip(),
        "user_agent": "WebExtractorAcademico/0.1 (+proyecto academico; contacto: configurar)",
        "authorization": {
            "confirmed": False, "authorized_by": None, "purpose": None, "terms_reviewed": False,
            "evidence_reference": None, "environment": "fixture" if local else "production",
            "allow_authentication": False, "personal_data": "none", "valid_until": None,
        },
        "scope": {
            "allowed_domains": [host] if host else [],
            "allowed_path_prefixes": [prefix or "/"],
            "allowed_schemes": [parts.scheme.lower()] if parts.scheme.lower() in ("http", "https") else ["https"],
            "allow_private_network": local,
            "respect_robots_txt": True,
        },
        "limits": {
            "max_pages": 2, "max_records": 50, "max_requests": 5, "max_seconds": 120,
            "delay_seconds": 0.5 if local else 3.0, "timeout_seconds": 15, "max_retries": 1,
            "max_clicks": 2, "max_scrolls": 2,
        },
        "diagnosis": {"max_requests": 3, "render_with_browser": False},
        "extraction": {"method": "auto", "fields": [{"name": "texto", "normalize": ["collapse_whitespace"]}]},
        "auth": {"type": "none"},
        "output": {"directory": "outputs", "formats": ["csv", "json", "excel", "sqlite"]},
    }


FIELD_COLUMNS = ["name", "selector", "attribute", "column", "path", "type", "required", "normalize",
                 "pattern", "date_format", "regex", "min", "max", "choices"]


def fields_to_rows(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aplana reglas de campos para un editor tabular."""
    rows = []
    for field in fields:
        rules = field.get("validate") or field.get("rules") or {}
        rows.append({
            "name": field.get("name", ""),
            "selector": field.get("selector") or "",
            "attribute": field.get("attribute") or "text",
            "column": field.get("column") or "",
            "path": field.get("path") or "",
            "type": field.get("type") or "string",
            "required": bool(field.get("required", False)),
            "normalize": list(field.get("normalize") or []),
            "pattern": field.get("pattern") or "",
            "date_format": field.get("date_format") or "",
            "regex": rules.get("regex") or "",
            "min": rules.get("min"),
            "max": rules.get("max"),
            "choices": ", ".join(rules.get("choices") or []),
        })
    return rows


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN de pandas
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def rows_to_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Inverso de ``fields_to_rows``; ignora filas sin nombre."""
    fields = []
    for row in rows:
        name = _clean(row.get("name"))
        if not name:
            continue
        field: dict[str, Any] = {"name": name, "type": _clean(row.get("type")) or "string",
                                 "attribute": _clean(row.get("attribute")) or "text",
                                 "required": bool(row.get("required") or False)}
        for key in ("selector", "column", "path", "pattern", "date_format"):
            if (value := _clean(row.get(key))) is not None:
                field[key] = value
        normalize = row.get("normalize") or []
        if isinstance(normalize, str):
            normalize = [n.strip() for n in normalize.split(",") if n.strip()]
        if normalize:
            field["normalize"] = list(normalize)
        rules: dict[str, Any] = {}
        if (regex := _clean(row.get("regex"))) is not None:
            rules["regex"] = regex
        for key in ("min", "max"):
            if (value := _clean(row.get(key))) is not None:
                rules[key] = float(value)
        if choices := _clean(row.get("choices")):
            rules["choices"] = [c.strip() for c in str(choices).split(",") if c.strip()]
        if rules:
            field["validate"] = rules
        fields.append(field)
    return fields
