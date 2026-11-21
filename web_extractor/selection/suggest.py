"""Sugerencias de reglas de extracción a partir del diagnóstico.

Son **borradores** para revisión humana: la detección automática puede equivocarse, por lo que
el usuario siempre puede escribir sus reglas a mano (modo manual) y validarlas con la vista
previa, incluso sobre un HTML guardado localmente.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from web_extractor.models.results import Diagnosis


def _field_name(text: str, used: set[str]) -> str:
    base = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_").lower() or "campo"
    if base[0].isdigit():
        base = f"c_{base}"
    name, i = base[:60], 2
    while name in used:
        name, i = f"{base[:57]}_{i}", i + 1
    used.add(name)
    return name


def suggest_extraction(diagnosis: Diagnosis) -> dict[str, Any] | None:
    """Devuelve un bloque ``extraction`` sugerido (dict) o ``None`` si no hay candidatos."""
    best = diagnosis.best.method if diagnosis.best else "static_html"
    cand = diagnosis.candidates
    used: set[str] = set()

    if cand.get("records_paths"):
        path = cand["records_paths"][0]["path"]
        fields = [{"name": _field_name(p, used), "path": p, "type": "string"}
                  for p in cand.get("json_fields", [])[:10]]
        if fields:
            fmt = cand.get("data_format", "json")
            method = "api" if best == "api" and fmt == "json" else "structured_file"
            block: dict[str, Any] = {"method": method, "records_path": None if path == "." else path, "fields": fields}
            if method == "structured_file":
                block["file_format"] = fmt
            return block
    if cand.get("csv_columns"):
        fields = [{"name": _field_name(c, used), "path": c, "type": "string"} for c in cand["csv_columns"][:15]]
        return {"method": "structured_file", "file_format": "csv", "fields": fields}

    tables = [t for t in cand.get("tables", []) if t["headers"]]
    records = cand.get("record_selectors", [])
    if tables and (not records or tables[0]["rows"] >= records[0]["count"]):
        table = tables[0]
        fields = [{"name": _field_name(h, used), "column": h, "type": "string", "normalize": ["collapse_whitespace"]}
                  for h in table["headers"][:15]]
        return {"method": "static_html" if best != "browser" else "browser",
                "table_selector": table["selector"], "fields": fields}
    if records:
        top = records[0]
        fields = []
        children = top["child_selectors"][:8]
        for child in sorted(children, key=lambda c: not _HEADING.match(c)):
            if _HEADING.match(child):
                fields.append({"name": _field_name("titulo", used), "selector": child,
                               "type": "string", "normalize": ["collapse_whitespace"]})
                continue
            cls = child.split(".", 1)[1] if "." in child else child
            fields.append({"name": _field_name(cls.split(".")[0], used), "selector": child,
                           "type": "string", "normalize": ["collapse_whitespace"]})
        if top.get("has_link"):
            fields.append({"name": _field_name("url", used), "selector": "a[href]", "attribute": "href", "type": "url"})
        if not fields:
            fields = [{"name": "texto", "type": "string", "normalize": ["collapse_whitespace"]}]
        method = best if best in ("static_html", "browser") else "static_html"
        block = {"method": method, "record_selector": top["selector"], "fields": fields}
        pagination = cand.get("pagination")
        if pagination and (method == "static_html" or pagination["mode"] == "next_link"):
            block["pagination"] = dict(pagination)
        return block
    return None


_HEADING = re.compile(r"^h[1-6](\.|$)")
