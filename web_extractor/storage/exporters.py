"""Exportadores. Solo reciben registros ya procesados y metadatos sin secretos.

- CSV: columnas de datos + columnas de linaje con prefijo ``_``.
- JSON: documento con metadatos de la ejecución y, por registro, ``data``/``raw``/``lineage``.
- SQLite: base local acumulativa con tablas ``runs``, ``records`` e ``incidents``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from web_extractor.models.results import Incident, ProcessedRecord

LINEAGE_COLUMNS = ("record_id", "run_id", "source_url", "retrieved_at", "method", "page_index", "validation_status")


@dataclass
class ExportBundle:
    run_id: str
    project: str
    field_names: list[str]
    records: list[ProcessedRecord]
    metadata: dict[str, Any] = field(default_factory=dict)
    incidents: list[Incident] = field(default_factory=list)


class Exporter(Protocol):
    name: str

    def export(self, bundle: ExportBundle, run_dir: Path) -> Path: ...


def to_dataframe(bundle: ExportBundle) -> pd.DataFrame:
    rows = []
    for record in bundle.records:
        row = {name: record.data.get(name) for name in bundle.field_names}
        for key in LINEAGE_COLUMNS:
            row[f"_{key}"] = record.lineage.get(key)
        row["_validation_errors"] = "; ".join(record.lineage.get("validation_errors", []))
        rows.append(row)
    columns = list(bundle.field_names) + [f"_{k}" for k in LINEAGE_COLUMNS] + ["_validation_errors"]
    return pd.DataFrame(rows, columns=columns)


class CsvExporter:
    name = "csv"

    def export(self, bundle: ExportBundle, run_dir: Path) -> Path:
        path = run_dir / "data.csv"
        to_dataframe(bundle).to_csv(path, index=False, encoding="utf-8")
        return path


class JsonExporter:
    name = "json"

    def export(self, bundle: ExportBundle, run_dir: Path) -> Path:
        path = run_dir / "data.json"
        document = {
            "run_id": bundle.run_id,
            "project": bundle.project,
            "metadata": bundle.metadata,
            "fields": bundle.field_names,
            "records": [r.to_dict() for r in bundle.records],
        }
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path


class SqliteExporter:
    name = "sqlite"

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY, project TEXT NOT NULL, target_url TEXT, method TEXT,
        status TEXT, started_at TEXT, finished_at TEXT, metadata_json TEXT
    );
    CREATE TABLE IF NOT EXISTS records (
        run_id TEXT NOT NULL REFERENCES runs(run_id), position INTEGER NOT NULL,
        record_id TEXT NOT NULL, validation_status TEXT, source_url TEXT, retrieved_at TEXT,
        data_json TEXT NOT NULL, raw_json TEXT, lineage_json TEXT NOT NULL,
        PRIMARY KEY (run_id, position)
    );
    CREATE INDEX IF NOT EXISTS idx_records_record_id ON records(record_id);
    CREATE TABLE IF NOT EXISTS incidents (
        run_id TEXT NOT NULL REFERENCES runs(run_id), timestamp TEXT, kind TEXT, severity TEXT,
        url TEXT, message TEXT, next_step TEXT
    );
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def export(self, bundle: ExportBundle, run_dir: Path) -> Path:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        meta = bundle.metadata
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (bundle.run_id, bundle.project, meta.get("target_url"), meta.get("method"), meta.get("status"),
                 meta.get("started_at"), meta.get("finished_at"), json.dumps(meta, ensure_ascii=False, default=str)),
            )
            conn.execute("DELETE FROM records WHERE run_id = ?", (bundle.run_id,))
            conn.executemany(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (bundle.run_id, i, r.lineage["record_id"], r.lineage["validation_status"], r.lineage["source_url"],
                     r.lineage["retrieved_at"], json.dumps(r.data, ensure_ascii=False, default=str),
                     json.dumps(r.raw, ensure_ascii=False, default=str),
                     json.dumps(r.lineage, ensure_ascii=False, default=str))
                    for i, r in enumerate(bundle.records)
                ],
            )
            conn.execute("DELETE FROM incidents WHERE run_id = ?", (bundle.run_id,))
            conn.executemany(
                "INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(bundle.run_id, i.timestamp, i.kind, i.severity, i.url, i.message, i.next_step) for i in bundle.incidents],
            )
        return self.db_path


EXPORTERS = ("csv", "json", "sqlite")


def export_all(bundle: ExportBundle, run_dir: Path, formats: list[str], sqlite_path: Path) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    exporters: dict[str, Exporter] = {"csv": CsvExporter(), "json": JsonExporter(), "sqlite": SqliteExporter(sqlite_path)}
    return {fmt: str(exporters[fmt].export(bundle, run_dir)) for fmt in formats}
