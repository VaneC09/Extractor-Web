"""Inspección de respuestas JSON/CSV: forma de los datos y rutas candidatas a lista de registros."""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

from web_extractor.inspectors.base import InspectionOutput
from web_extractor.models.results import FetchedDocument, Finding
from web_extractor.selection.paths import get_path, key_paths


def _list_paths(data: Any, prefix: str = "", depth: int = 3) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    if isinstance(data, list) and data and isinstance(data[0], dict):
        found.append((prefix.rstrip(".") or ".", len(data)))
    if isinstance(data, dict) and depth > 0:
        for key, value in data.items():
            found.extend(_list_paths(value, f"{prefix}{key}.", depth - 1))
    return found


class StructuredInspector:
    name = "structured"

    def applies_to(self, doc: FetchedDocument) -> bool:
        return doc.is_json or doc.is_csv

    def inspect(self, doc: FetchedDocument) -> InspectionOutput:
        out = InspectionOutput()
        if doc.is_json:
            try:
                data = json.loads(doc.text)
            except json.JSONDecodeError as exc:
                out.findings.append(Finding("json.invalid", "estructurado", "El JSON no se puede interpretar", str(exc)))
                return out
            lists = _list_paths(data)
            out.candidates["records_paths"] = [{"path": p, "count": n} for p, n in lists]
            if lists:
                path, count = lists[0]
                sample = get_path(data, None if path == "." else path)
                fields = key_paths(sample[0]) if sample else []
                out.candidates["json_fields"] = fields
                out.findings.append(Finding("json.records", "estructurado",
                                            f"Lista de {count} objetos en '{path}'", ", ".join(fields[:12])))
            if isinstance(data, dict):
                nexts = [k for k in key_paths(data, depth=2) if k.split(".")[-1] in ("next", "next_page", "nextPage")]
                if nexts:
                    out.findings.append(Finding("json.next", "paginación", "Campo de siguiente página en JSON",
                                                ", ".join(nexts), {"api": 0.1}))
                    out.candidates["next_fields"] = nexts
        else:
            try:
                frame = pd.read_csv(io.StringIO(doc.text), dtype=str, nrows=50)
                out.candidates["csv_columns"] = list(frame.columns)
                out.findings.append(Finding("csv.columns", "estructurado", f"CSV con {len(frame.columns)} columnas",
                                            ", ".join(map(str, frame.columns[:15]))))
            except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
                out.findings.append(Finding("csv.invalid", "estructurado", "El CSV no se puede interpretar", str(exc)))
        return out
