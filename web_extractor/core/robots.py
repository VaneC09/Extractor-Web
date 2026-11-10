"""Respeto de robots.txt (RFC 9309) como política de acceso publicada.

- 2xx: se interpreta el archivo.
- 4xx (no existe / no disponible): se permite el acceso (comportamiento del RFC).
- 5xx o error de red: se asume prohibición total (comportamiento conservador del RFC).

robots.txt **no** sustituye a los términos de uso ni a la autorización del propietario: es solo
una política adicional que se respeta.
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from web_extractor.core.errors import RobotsDisallowed

Fetcher = Callable[[str], tuple[int | None, str]]


class RobotsPolicy:
    def __init__(self, fetcher: Fetcher, user_agent: str, on_crawl_delay: Callable[[float], None] | None = None):
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._on_crawl_delay = on_crawl_delay
        self._parsers: dict[str, RobotFileParser | bool] = {}
        self.notes: list[str] = []

    @staticmethod
    def origin(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    def _load(self, origin: str) -> RobotFileParser | bool:
        status, text = self._fetcher(origin + "/robots.txt")
        if status is None or status >= 500:
            self.notes.append(f"{origin}/robots.txt no disponible (estado {status}): se asume prohibición total")
            return False
        if 400 <= status < 500:
            self.notes.append(f"{origin}/robots.txt devolvió {status}: sin restricciones publicadas")
            return True
        parser = RobotFileParser()
        parser.parse(text.splitlines())
        delay = parser.crawl_delay(self._user_agent)
        if delay and self._on_crawl_delay:
            self._on_crawl_delay(float(delay))
            self.notes.append(f"Crawl-delay {delay}s aplicado")
        self.notes.append(f"{origin}/robots.txt leído")
        return parser

    def is_allowed(self, url: str) -> bool:
        origin = self.origin(url)
        if origin not in self._parsers:
            self._parsers[origin] = self._load(origin)
        policy = self._parsers[origin]
        if isinstance(policy, bool):
            return policy
        return policy.can_fetch(self._user_agent, url)

    def ensure_allowed(self, url: str) -> None:
        if not self.is_allowed(url):
            raise RobotsDisallowed(f"robots.txt no permite acceder a {url}")
