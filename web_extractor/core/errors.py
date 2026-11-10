"""Jerarquía de excepciones. Cada una corresponde a una decisión de parada distinta."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from web_extractor.core.barriers import Barrier


class WebExtractorError(Exception):
    """Base de todos los errores controlados de la herramienta."""


class ConfigError(WebExtractorError):
    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("Configuración inválida:\n- " + "\n- ".join(messages))


class ScopeError(WebExtractorError):
    """La URL no está dentro del alcance autorizado (protocolo, dominio, ruta o red)."""


class AuthorizationError(WebExtractorError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Falta autorización o confirmación:\n- " + "\n- ".join(missing))


class RobotsDisallowed(WebExtractorError):
    """robots.txt no permite la ruta para nuestro agente."""


class BarrierDetected(WebExtractorError):
    """CAPTCHA, bloqueo, límite de tasa, autenticación no autorizada, etc. Nunca se reintenta."""

    def __init__(self, barrier: "Barrier"):
        self.barrier = barrier
        super().__init__(f"Barrera detectada ({barrier.kind}): {barrier.message}")


class LimitReached(WebExtractorError):
    def __init__(self, limit: str, detail: str = ""):
        self.limit = limit
        super().__init__(f"Límite alcanzado: {limit}" + (f" ({detail})" if detail else ""))


class Cancelled(WebExtractorError):
    def __init__(self, reason: str = "cancelado por el usuario"):
        self.reason = reason
        super().__init__(f"Ejecución cancelada: {reason}")


class TransientHTTPError(WebExtractorError):
    """Fallo de red/servidor transitorio que persistió tras los reintentos permitidos."""


class HTTPStatusError(WebExtractorError):
    def __init__(self, status: int, url: str):
        self.status = status
        self.url = url
        super().__init__(f"Respuesta HTTP {status} en {url}")


class AuthFailed(WebExtractorError):
    """La autenticación autorizada no fue aceptada. No se reintenta con otras credenciales."""


class ExtractionError(WebExtractorError):
    """Error al interpretar un documento con las reglas configuradas."""


class BrowserUnavailable(WebExtractorError):
    """Selenium o el navegador no están disponibles en el entorno."""
