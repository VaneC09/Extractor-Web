"""Convierte un documento en registros crudos según las reglas de la configuración.

Un único motor de selección sirve para todos los adaptadores: el navegador entrega el HTML
renderizado y se procesa igual que una respuesta estática. No hay selectores de ningún sitio
concreto en este módulo; todos provienen de la configuración.
"""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup, Tag

from web_extractor.config.schema import ExtractionConfig, FieldRule
from web_extractor.core.errors import ExtractionError
from web_extractor.models.results import FetchedDocument, ParseResult
from web_extractor.selection.paths import get_path, key_paths

_URL_ATTRIBUTES = {"href", "src", "action", "data-href", "data-src", "poster"}


def _element_value(target: Tag | None, rule: FieldRule, base_url: str) -> Any:
    if target is None:
        return None
    if rule.attribute == "text":
        return target.get_text(" ", strip=True)
    if rule.attribute == "html":
        return target.decode_contents().strip()
    value = target.get(rule.attribute)
    if isinstance(value, list):
        value = " ".join(value)
    if value and rule.attribute in _URL_ATTRIBUTES:
        value = urljoin(base_url, value)
    return value


def _structure_of(element: Tag, limit: int = 40) -> list[str]:
    tokens = set()
    for child in element.find_all(True):
        classes = ".".join(sorted(child.get("class", [])))
        tokens.add(f"{child.name}.{classes}" if classes else child.name)
        if len(tokens) >= limit:
            break
    return sorted(tokens)


def parse_html_records(html: str, base_url: str, extraction: ExtractionConfig) -> ParseResult:
    soup = BeautifulSoup(html, "html.parser")
    if extraction.table_selector:
        return parse_html_table(soup, extraction)
    assert extraction.record_selector
    try:
        elements = soup.select(extraction.record_selector)
    except Exception as exc:  # soupsieve lanza SelectorSyntaxError
        raise ExtractionError(f"record_selector inválido '{extraction.record_selector}': {exc}") from None
    items = []
    for element in elements:
        item = {}
        for rule in extraction.fields:
            target = element.select_one(rule.selector) if rule.selector else element
            item[rule.name] = _element_value(target, rule, base_url)
        items.append(item)
    return ParseResult(items, _structure_of(elements[0]) if elements else [])


def parse_html_table(soup: BeautifulSoup, extraction: ExtractionConfig) -> ParseResult:
    table = soup.select_one(extraction.table_selector or "table")
    if table is None:
        return ParseResult([], [])
    rows = table.find_all("tr")
    header_row = next((r for r in rows if r.find("th")), rows[0] if rows else None)
    if header_row is None:
        return ParseResult([], [])
    headers = [" ".join(c.get_text(" ", strip=True).split()) for c in header_row.find_all(["th", "td"])]
    lookup = {h.lower(): i for i, h in enumerate(headers)}
    items = []
    for row in rows:
        if row is header_row:
            continue
        cells = row.find_all(["td", "th"])
        if not cells or not row.find("td"):
            continue
        item = {}
        for rule in extraction.fields:
            index = lookup.get((rule.column or "").lower())
            cell = cells[index] if index is not None and index < len(cells) else None
            target = cell.select_one(rule.selector) if (cell is not None and rule.selector) else cell
            item[rule.name] = _element_value(target, rule, "")
        items.append(item)
    return ParseResult(items, [f"column:{h}" for h in headers])


def parse_json_records(text: str, extraction: ExtractionConfig) -> ParseResult:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"JSON inválido: {exc}") from None
    records = get_path(data, extraction.records_path)
    if records is None:
        raise ExtractionError(f"records_path '{extraction.records_path}' no existe en la respuesta")
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ExtractionError(f"records_path '{extraction.records_path}' no es una lista")
    items = [{rule.name: get_path(rec, rule.path) for rule in extraction.fields} for rec in records]
    structure = key_paths(records[0]) if records and isinstance(records[0], dict) else []
    return ParseResult(items, structure)


def parse_csv_records(text: str, extraction: ExtractionConfig) -> ParseResult:
    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ExtractionError(f"CSV inválido: {exc}") from None
    frame.columns = [str(c).strip() for c in frame.columns]
    items = [
        {rule.name: row.get(rule.path) for rule in extraction.fields}
        for row in frame.to_dict(orient="records")
    ]
    return ParseResult(items, [f"column:{c}" for c in frame.columns])


def detect_format(doc: FetchedDocument, extraction: ExtractionConfig) -> str:
    if extraction.file_format:
        return extraction.file_format
    if extraction.method == "api" or doc.is_json:
        return "json"
    if doc.is_csv:
        return "csv"
    return "html"


def parse_document(doc: FetchedDocument, extraction: ExtractionConfig) -> ParseResult:
    fmt = detect_format(doc, extraction)
    if fmt == "json":
        return parse_json_records(doc.text, extraction)
    if fmt == "csv":
        return parse_csv_records(doc.text, extraction)
    if not (extraction.record_selector or extraction.table_selector):
        raise ExtractionError("Para HTML se requiere record_selector o table_selector")
    return parse_html_records(doc.text, doc.final_url, extraction)
