"""Canalización de calidad: normalizar -> patrón -> tipo -> validar -> deduplicar -> linaje.

Estados de validación por registro:
- ``valido``: todos los campos correctos.
- ``advertencia``: algún campo opcional vacío o inválido (se conserva como ``None``).
- ``invalido``: falta un campo obligatorio o no supera su validación.

Se conserva el valor crudo (``raw``) junto al procesado si ``extraction.keep_raw`` es true, y el
linaje registra URL de origen, fecha, ejecución, método, estado y pasos aplicados por campo.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pandas as pd

from web_extractor.config.schema import ExtractionConfig, FieldRule
from web_extractor.models.results import FieldQuality, ProcessedRecord, QualityReport, RawRecord
from web_extractor.transforms.casting import CastError, cast_value
from web_extractor.transforms.normalizers import apply_normalizer
from web_extractor.transforms.validators import validate_value

MAX_ERROR_SAMPLES = 25


def process_field(rule: FieldRule, raw: Any) -> tuple[Any, list[str], list[str]]:
    """Devuelve (valor_procesado, pasos_aplicados, errores)."""
    steps: list[str] = []
    errors: list[str] = []
    value = raw
    for name in rule.normalize:
        value = apply_normalizer(name, value)
        steps.append(name)
    if rule.pattern and isinstance(value, str):
        match = re.search(rule.pattern, value)
        steps.append("pattern")
        if match:
            value = match.group(1) if match.groups() else match.group(0)
        else:
            errors.append(f"{rule.name}: patrón {rule.pattern!r} no coincide con {value!r}")
            value = None
    if isinstance(value, str) and value.strip() == "":
        value = None
    if value is not None:
        try:
            value = cast_value(value, rule.type, rule.date_format)
            steps.append(f"cast:{rule.type}")
        except CastError as exc:
            errors.append(f"{rule.name}: {exc}")
            value = None
    if value is not None:
        problems = validate_value(value, rule.rules)
        if problems:
            steps.append("validate")
            errors.extend(f"{rule.name}: {p}" for p in problems)
            value = None
    return value, steps, errors


def _record_id(data: dict[str, Any], keys: list[str]) -> str:
    payload = json.dumps({k: data.get(k) for k in keys}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class TransformPipeline:
    def __init__(self, extraction: ExtractionConfig) -> None:
        self.extraction = extraction
        self.dedup_keys = extraction.deduplicate_on or [f.name for f in extraction.fields]

    def process(self, raw_records: list[RawRecord], run_id: str,
                provenance: dict[str, Any] | None = None) -> tuple[list[ProcessedRecord], QualityReport]:
        quality = QualityReport(total_raw=len(raw_records),
                                fields={f.name: FieldQuality() for f in self.extraction.fields})
        processed: list[ProcessedRecord] = []
        for position, raw in enumerate(raw_records):
            data: dict[str, Any] = {}
            transformations: dict[str, list[str]] = {}
            errors: list[str] = []
            status = "valido"
            for rule in self.extraction.fields:
                raw_value = raw.values.get(rule.name)
                value, steps, field_errors = process_field(rule, raw_value)
                data[rule.name] = value
                transformations[rule.name] = steps
                fq = quality.fields[rule.name]
                if field_errors:
                    fq.invalid += 1
                    errors.extend(field_errors)
                if value is None:
                    fq.empty += 1
                    if rule.required:
                        status = "invalido"
                        if not field_errors:
                            errors.append(f"{rule.name}: obligatorio y vacío")
                    elif status == "valido":
                        status = "advertencia"
                else:
                    fq.filled += 1
            lineage = {
                "record_id": _record_id(data, self.dedup_keys),
                "run_id": run_id,
                "position": position,
                "source_url": raw.source_url,
                "retrieved_at": raw.retrieved_at,
                "method": raw.method,
                "page_index": raw.page_index,
                "validation_status": status,
                "validation_errors": errors,
                "transformations": transformations,
                **(provenance or {}),
            }
            for err in errors:
                if len(quality.error_samples) < MAX_ERROR_SAMPLES:
                    quality.error_samples.append(f"#{position} ({raw.source_url}): {err}")
            processed.append(ProcessedRecord(data, dict(raw.values) if self.extraction.keep_raw else {}, lineage))

        processed = self._deduplicate(processed, quality)
        if self.extraction.drop_invalid:
            kept = [r for r in processed if r.lineage["validation_status"] != "invalido"]
            quality.dropped_invalid = len(processed) - len(kept)
            processed = kept
        for record in processed:
            status = record.lineage["validation_status"]
            if status == "valido":
                quality.valid += 1
            elif status == "advertencia":
                quality.with_warnings += 1
            else:
                quality.invalid += 1
        quality.exported = len(processed)
        return processed, quality

    def _deduplicate(self, records: list[ProcessedRecord], quality: QualityReport) -> list[ProcessedRecord]:
        if not records:
            return records
        frame = pd.DataFrame(
            [{k: json.dumps(r.data.get(k), sort_keys=True, default=str) for k in self.dedup_keys} for r in records]
        )
        duplicated = frame.duplicated(keep="first").tolist()
        quality.duplicates_removed = sum(duplicated)
        return [r for r, dup in zip(records, duplicated) if not dup]
