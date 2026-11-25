"""Topes explícitos, pausas entre solicitudes y cancelación cooperativa.

- ``CancelToken``: se activa con Ctrl+C (CLI), desde código o creando el archivo STOP en el
  directorio de salida. Todas las esperas consultan el token, por lo que la parada es inmediata
  entre acciones (una solicitud HTTP ya iniciada termina o expira por timeout).
- ``Budget``: contadores de solicitudes, páginas, registros, clics, scrolls y tiempo.
- ``RateLimiter``: pausa mínima entre solicitudes; concurrencia fija en 1.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from web_extractor.core.errors import Cancelled, LimitReached


class CancelToken:
    def __init__(self, stop_file: Path | None = None) -> None:
        self._event = threading.Event()
        self.reason = ""
        self.stop_file = stop_file

    def cancel(self, reason: str = "cancelado por el usuario") -> None:
        if not self._event.is_set():
            self.reason = reason
            self._event.set()

    @property
    def cancelled(self) -> bool:
        if not self._event.is_set() and self.stop_file is not None and self.stop_file.exists():
            self.cancel(f"archivo de parada detectado: {self.stop_file}")
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise Cancelled(self.reason)

    def wait(self, seconds: float) -> None:
        """Duerme hasta ``seconds`` pero despierta en cuanto se cancela."""
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            self.raise_if_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._event.wait(min(remaining, 0.1))


@dataclass
class LimitValues:
    max_pages: int
    max_records: int
    max_requests: int
    max_seconds: float
    max_clicks: int = 0
    max_scrolls: int = 0


class Budget:
    def __init__(self, limits: LimitValues, cancel: CancelToken) -> None:
        self.limits = limits
        self.cancel = cancel
        self.started = time.monotonic()
        self.paused = 0.0
        self.requests = 0
        self.pages = 0
        self.records = 0
        self.clicks = 0
        self.scrolls = 0

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started - self.paused

    @contextmanager
    def pause(self) -> Iterator[None]:
        """El tiempo que una persona tarda en intervenir no cuenta para ``max_seconds``."""
        start = time.monotonic()
        try:
            yield
        finally:
            self.paused += time.monotonic() - start

    def check(self) -> None:
        self.cancel.raise_if_cancelled()
        if self.elapsed > self.limits.max_seconds:
            raise LimitReached("max_seconds", f"{self.elapsed:.1f}s > {self.limits.max_seconds}s")

    def consume_request(self) -> None:
        self.check()
        if self.requests >= self.limits.max_requests:
            raise LimitReached("max_requests", str(self.limits.max_requests))
        self.requests += 1

    def consume_page(self) -> None:
        self.check()
        if self.pages >= self.limits.max_pages:
            raise LimitReached("max_pages", str(self.limits.max_pages))
        self.pages += 1

    def consume_click(self) -> None:
        self.check()
        if self.clicks >= self.limits.max_clicks:
            raise LimitReached("max_clicks", str(self.limits.max_clicks))
        self.clicks += 1

    def consume_scroll(self) -> None:
        self.check()
        if self.scrolls >= self.limits.max_scrolls:
            raise LimitReached("max_scrolls", str(self.limits.max_scrolls))
        self.scrolls += 1

    @property
    def records_remaining(self) -> int:
        return max(0, self.limits.max_records - self.records)

    def add_records(self, count: int = 1) -> None:
        self.records += count

    def snapshot(self) -> dict[str, float | int]:
        return {
            "requests": self.requests,
            "pages": self.pages,
            "records": self.records,
            "clicks": self.clicks,
            "scrolls": self.scrolls,
            "elapsed_seconds": round(self.elapsed, 2),
            "max_requests": self.limits.max_requests,
            "max_pages": self.limits.max_pages,
            "max_records": self.limits.max_records,
            "max_seconds": self.limits.max_seconds,
        }


class RateLimiter:
    def __init__(self, delay_seconds: float, cancel: CancelToken) -> None:
        self.delay = max(0.0, delay_seconds)
        self.cancel = cancel
        self._last: float | None = None

    def raise_min_delay(self, seconds: float) -> None:
        """Aplica un retardo mayor si el sitio lo solicita (p. ej. Crawl-delay)."""
        self.delay = max(self.delay, seconds)

    def wait_turn(self) -> None:
        if self._last is not None:
            remaining = self.delay - (time.monotonic() - self._last)
            if remaining > 0:
                self.cancel.wait(remaining)
        self.cancel.raise_if_cancelled()
        self._last = time.monotonic()
