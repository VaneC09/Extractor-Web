"""Registro de acciones (trazabilidad) e incidencias de una ejecución."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from web_extractor.models.results import Incident
from web_extractor.utils.redaction import redact, redact_url
from web_extractor.utils.timeutils import utc_now_iso


@dataclass
class ActionEntry:
    action: str
    target: str = ""
    detail: str = ""
    outcome: str = "ok"
    timestamp: str = field(default_factory=utc_now_iso)


class ActionLog:
    """Cada solicitud, clic, scroll o decisión de parada queda registrada (sin secretos)."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.entries: list[ActionEntry] = []
        self.logger = logger

    def record(self, action: str, target: str = "", detail: str = "", outcome: str = "ok") -> None:
        entry = ActionEntry(action, redact_url(target), redact(detail), outcome)
        self.entries.append(entry)
        if self.logger:
            self.logger.info("[%s] %s %s %s", outcome, action, entry.target, entry.detail)

    def write_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for entry in self.entries:
                fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


class IncidentLog:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.items: list[Incident] = []
        self.logger = logger

    def add(self, kind: str, message: str, url: str = "", next_step: str = "", severity: str = "alta") -> Incident:
        incident = Incident(kind, redact(message), redact_url(url), redact(next_step), severity)
        self.items.append(incident)
        if self.logger:
            self.logger.warning("INCIDENCIA %s: %s %s", kind, incident.message, incident.url)
        return incident
