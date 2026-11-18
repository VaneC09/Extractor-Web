"""Cliente HTTP respetuoso: alcance, robots.txt, presupuesto, pausas, reintentos acotados y barreras.

Orden de comprobaciones en cada solicitud:
1. cancelación y tiempo máximo;  2. alcance de la URL;  3. robots.txt;
4. presupuesto de solicitudes;   5. pausa mínima;       6. solicitud con timeout;
7. redirecciones manuales (cada salto se valida contra el alcance);
8. detección de barreras -> parada inmediata (sin reintento);
9. reintentos solo para fallos transitorios (errores de red, 502, 504), con tope.
"""

from __future__ import annotations

import codecs
import logging
import re
from typing import Mapping
from urllib.parse import urljoin

import requests

from web_extractor.config.schema import ProjectConfig
from web_extractor.core.barriers import detect_barrier
from web_extractor.core.errors import BarrierDetected, HTTPStatusError, ScopeError, TransientHTTPError
from web_extractor.core.limits import Budget, CancelToken, RateLimiter
from web_extractor.core.robots import RobotsPolicy
from web_extractor.core.scope import check_in_scope, validate_url
from web_extractor.core.tracing import ActionLog
from web_extractor.models.results import FetchedDocument
from web_extractor.utils.timeutils import utc_now_iso

TRANSIENT_STATUS = {502, 504}
MAX_REDIRECTS = 5
_SAFE_HEADERS = ("content-type", "content-length", "last-modified", "etag", "link", "retry-after",
                 "x-ratelimit-limit", "x-ratelimit-remaining", "cache-control", "x-robots-tag")


class PoliteHttpClient:
    def __init__(
        self,
        cfg: ProjectConfig,
        budget: Budget,
        rate: RateLimiter,
        cancel: CancelToken,
        actions: ActionLog,
        logger: logging.Logger | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.cfg = cfg
        self.budget = budget
        self.rate = rate
        self.cancel = cancel
        self.actions = actions
        self.logger = logger or logging.getLogger("web_extractor.http")
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": cfg.user_agent, "Accept-Language": "es,en;q=0.7"})
        self.robots = RobotsPolicy(self._fetch_robots, cfg.user_agent, rate.raise_min_delay)
        # Encabezados de autenticación autorizada: solo en solicitudes dentro del alcance, nunca a robots.txt.
        self.auth_headers: dict[str, str] = {}

    def close(self) -> None:
        self.session.close()

    def _fetch_robots(self, url: str) -> tuple[int | None, str]:
        try:
            doc = self._request("GET", url, purpose="robots.txt", check_barriers=False,
                                raise_for_status=False, check_robots=False)
            return doc.status, doc.text
        except ScopeError as exc:
            self.robots.reasons[RobotsPolicy.origin(url)] = (
                f"robots.txt redirige fuera del alcance ({exc}); se asume prohibición total. Si el propietario "
                "autoriza ese dominio (p. ej. la variante con o sin 'www'), añádalo a scope.allowed_domains."
            )
            return None, ""
        except (TransientHTTPError, HTTPStatusError):
            return None, ""

    def ensure_allowed(self, url: str) -> None:
        """Comprobación de alcance + robots.txt reutilizable por el adaptador de navegador."""
        check_in_scope(url, self.cfg.scope)
        if self.cfg.scope.respect_robots_txt:
            self.robots.ensure_allowed(url)

    def get(self, url: str, purpose: str, *, accept: str | None = None, auth_expected: bool = False) -> FetchedDocument:
        headers = {"Accept": accept} if accept else None
        return self._request("GET", url, purpose=purpose, headers=headers, auth_expected=auth_expected)

    def post_form(self, url: str, data: Mapping[str, str], purpose: str) -> FetchedDocument:
        return self._request("POST", url, purpose=purpose, data=dict(data), auth_expected=True,
                             raise_for_status=False)

    def _request(
        self,
        method: str,
        url: str,
        *,
        purpose: str,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        check_barriers: bool = True,
        auth_expected: bool = False,
        raise_for_status: bool = True,
        check_robots: bool = True,
    ) -> FetchedDocument:
        limits = self.cfg.limits
        original_url = url
        attempts = 0
        redirects = 0
        while True:
            self.budget.check()
            try:
                if check_robots:
                    check_in_scope(url, self.cfg.scope)
                else:
                    validate_url(url, allowed_schemes=self.cfg.scope.allowed_schemes,
                                 allowed_domains=self.cfg.scope.allowed_domains, allowed_path_prefixes=["/robots.txt"],
                                 allow_private_network=self.cfg.scope.allow_private_network)
            except ScopeError as exc:
                if not redirects:
                    raise
                self.actions.record("redirect_blocked", url, f"desde {original_url}", "stop")
                raise ScopeError(
                    f"{original_url} redirige a {url}, que está fuera del alcance autorizado ({exc}). No se siguió "
                    "la redirección. Si el propietario autoriza ese destino (p. ej. la variante con o sin 'www', "
                    "o https), añádalo explícitamente al alcance."
                ) from None
            if check_robots and self.cfg.scope.respect_robots_txt:
                self.robots.ensure_allowed(url)
            self.budget.consume_request()
            self.rate.wait_turn()
            send_headers = {**(headers or {}), **self.auth_headers} if check_robots else headers
            try:
                response = self.session.request(
                    method, url, headers=send_headers, data=data, timeout=limits.timeout_seconds,
                    allow_redirects=False, stream=True,
                )
                text, truncated = self._read_limited(response)
            except (requests.ConnectionError, requests.Timeout) as exc:
                self.actions.record(f"http_{method.lower()}", url, f"{purpose}: {type(exc).__name__}", "error")
                if attempts < limits.max_retries:
                    attempts += 1
                    self.cancel.wait(min(30.0, max(1.0, limits.delay_seconds) * 2**attempts))
                    continue
                raise TransientHTTPError(f"Fallo de red persistente en {url}: {type(exc).__name__}") from None

            status = response.status_code
            self.actions.record(f"http_{method.lower()}", url, f"{purpose} -> {status}",
                                "ok" if status < 400 else "error")

            if status in (301, 302, 303, 307, 308) and "location" in response.headers:
                redirects += 1
                if redirects > MAX_REDIRECTS:
                    raise HTTPStatusError(status, url)
                url = urljoin(url, response.headers["location"])
                if status == 303 or (status in (301, 302) and method == "POST"):
                    method, data = "GET", None
                continue

            if status in TRANSIENT_STATUS and attempts < limits.max_retries:
                attempts += 1
                self.cancel.wait(min(30.0, max(1.0, limits.delay_seconds) * 2**attempts))
                continue

            safe_headers = {k: v for k, v in response.headers.items() if k.lower() in _SAFE_HEADERS}
            if check_barriers:
                barrier = detect_barrier(status, safe_headers, text, auth_expected=auth_expected)
                if barrier:
                    barrier.url = url
                    self.actions.record("barrier_detected", url, f"{barrier.kind}: {barrier.message}", "stop")
                    raise BarrierDetected(barrier)
            if raise_for_status and status >= 400:
                raise HTTPStatusError(status, url)
            return FetchedDocument(
                url=original_url,
                final_url=url,
                status=status,
                content_type=response.headers.get("content-type", "").lower(),
                text=text,
                fetched_at=utc_now_iso(),
                headers=safe_headers,
                via="http",
                truncated=truncated,
            )

    def _read_limited(self, response: requests.Response) -> tuple[str, bool]:
        max_bytes = self.cfg.limits.max_response_bytes
        chunks: list[bytes] = []
        size = 0
        truncated = False
        for chunk in response.iter_content(chunk_size=65536):
            chunks.append(chunk)
            size += len(chunk)
            if size >= max_bytes:
                truncated = True
                break
        response.close()
        raw = b"".join(chunks)[:max_bytes]
        return raw.decode(detect_encoding(response.headers.get("content-type", ""), raw), errors="replace"), truncated


_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]+)""", re.I)


def detect_encoding(content_type: str, raw: bytes) -> str:
    """Cabecera ``charset`` > ``<meta charset>`` del documento > UTF-8 (válido) > windows-1252."""
    candidates = []
    if match := re.search(r"charset\s*=\s*[\"']?([\w.:-]+)", content_type, re.I):
        candidates.append(match.group(1))
    if match := _META_CHARSET.search(raw[:4096]):
        candidates.append(match.group(1).decode("ascii", "ignore"))
    for name in candidates:
        try:
            codecs.lookup(name)
            return name
        except LookupError:
            continue
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "windows-1252"
