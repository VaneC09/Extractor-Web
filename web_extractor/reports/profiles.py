"""Perfiles reutilizables por sitio y comparación entre ejecuciones.

El perfil resume una ejecución aceptada (método, reglas, tasa de llenado por campo, volumen y
firma estructural). Al comparar, se señalan cambios con severidad; si alguno es ``alta`` se
exige revisión humana y **no** se actualiza la línea base ni se corrige ningún selector.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web_extractor.config.schema import ProjectConfig
from web_extractor.models.results import QualityReport
from web_extractor.utils.timeutils import utc_now_iso

FILL_DROP_THRESHOLD = 0.3
VOLUME_CHANGE_THRESHOLD = 0.5


def build_profile(cfg: ProjectConfig, run_id: str, quality: QualityReport, structure: list[str]) -> dict[str, Any]:
    total = quality.total_raw
    return {
        "profile_name": cfg.profile_name,
        "saved_at": utc_now_iso(),
        "run_id": run_id,
        "target_url": cfg.target_url,
        "method": cfg.extraction.method,
        "record_selector": cfg.extraction.record_selector,
        "table_selector": cfg.extraction.table_selector,
        "records_path": cfg.extraction.records_path,
        "record_count": total,
        "max_records": cfg.limits.max_records,
        "fields": {
            f.name: {
                "selector": f.selector, "path": f.path, "column": f.column, "attribute": f.attribute,
                "type": f.type, "fill_rate": quality.fields[f.name].fill_rate(total) if f.name in quality.fields else 0.0,
            }
            for f in cfg.extraction.fields
        },
        "structure": sorted(structure),
    }


def compare_profiles(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    def add(kind: str, severity: str, message: str) -> None:
        changes.append({"kind": kind, "severity": severity, "message": message})

    for key in ("target_url", "method", "record_selector", "table_selector", "records_path"):
        if previous.get(key) != current.get(key):
            add("config", "media", f"{key} cambió: {previous.get(key)!r} -> {current.get(key)!r}")

    prev_fields, curr_fields = previous.get("fields", {}), current.get("fields", {})
    for name in sorted(set(prev_fields) - set(curr_fields)):
        add("field_removed", "media", f"campo desaparecido de la configuración: {name}")
    for name in sorted(set(curr_fields) - set(prev_fields)):
        add("field_added", "baja", f"campo nuevo en la configuración: {name}")
    for name in sorted(set(prev_fields) & set(curr_fields)):
        p, c = prev_fields[name], curr_fields[name]
        for key in ("selector", "path", "column", "attribute", "type"):
            if p.get(key) != c.get(key):
                add("rule_changed", "media", f"{name}.{key}: {p.get(key)!r} -> {c.get(key)!r}")
        drop = (p.get("fill_rate") or 0) - (c.get("fill_rate") or 0)
        if drop >= FILL_DROP_THRESHOLD:
            add("fill_rate_drop", "alta", f"{name}: tasa de llenado {p['fill_rate']:.0%} -> {c['fill_rate']:.0%} "
                                          "(posible selector roto o cambio de estructura)")

    prev_n, curr_n = previous.get("record_count", 0), current.get("record_count", 0)
    if prev_n and curr_n == 0:
        add("volume", "alta", f"sin registros (antes {prev_n})")
    elif prev_n and abs(curr_n - prev_n) / prev_n >= VOLUME_CHANGE_THRESHOLD:
        add("volume", "media", f"volumen {prev_n} -> {curr_n} ({(curr_n - prev_n) / prev_n:+.0%})")

    prev_s, curr_s = set(previous.get("structure", [])), set(current.get("structure", []))
    removed, added = sorted(prev_s - curr_s), sorted(curr_s - prev_s)
    if removed:
        severity = "alta" if prev_s and len(removed) / len(prev_s) > 0.5 else "media"
        add("structure_removed", severity, f"elementos/columnas/claves desaparecidos: {removed[:10]}")
    if added:
        add("structure_added", "baja", f"elementos/columnas/claves nuevos: {added[:10]}")
    return changes


def requires_review(changes: list[dict[str, Any]]) -> bool:
    return any(c["severity"] == "alta" for c in changes)


class ProfileStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def load(self, name: str) -> dict[str, Any] | None:
        path = self.path_for(name)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def save(self, name: str, profile: dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(name)
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
