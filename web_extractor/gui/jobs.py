"""Extracción en segundo plano para la GUI, con progreso en vivo y cancelación cooperativa."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from web_extractor.config.schema import ProjectConfig
from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.limits import CancelToken
from web_extractor.core.tracing import ActionEntry
from web_extractor.models.results import RunResult

_REQUEST_ACTIONS = {"http_get", "http_post", "browser_get", "click", "scroll"}


@dataclass
class ExtractionJob:
    cfg: ProjectConfig
    cancel: CancelToken = field(default_factory=CancelToken)
    entries: list[ActionEntry] = field(default_factory=list)
    result: RunResult | None = None
    error: str | None = None
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True, name="extraccion-gui")

    def _record(self, entry: ActionEntry) -> None:
        with self._lock:
            self.entries.append(entry)

    def _run(self) -> None:
        try:
            engine = ExtractionEngine(self.cfg, cancel=self.cancel, on_action=self._record)
            self.result = engine.run(confirmed=True)
        except Exception as exc:  # se muestra en la interfaz; el motor ya registró el detalle
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.finished = time.monotonic()

    def start(self) -> "ExtractionJob":
        self._thread.start()
        return self

    def request_cancel(self) -> None:
        self.cancel.cancel("cancelado desde la interfaz gráfica")

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    @property
    def elapsed(self) -> float:
        return (self.finished or time.monotonic()) - self.started

    def snapshot(self) -> list[ActionEntry]:
        with self._lock:
            return list(self.entries)

    def counters(self) -> dict[str, int]:
        entries = self.snapshot()
        return {
            "solicitudes": sum(e.action in _REQUEST_ACTIONS for e in entries),
            "paginas": sum(e.action == "parse" for e in entries),
            "registros": sum(int(e.detail.split()[0]) for e in entries if e.action == "parse" and e.detail[:1].isdigit()),
            "clics": sum(e.action == "click" for e in entries),
            "scrolls": sum(e.action == "scroll" for e in entries),
        }
