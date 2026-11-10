"""Redacción de secretos para logs, informes y evidencias.

Dos capas:
1. ``SECRETS``: registro en memoria de valores concretos (p. ej. la contraseña leída de una
   variable de entorno) que se sustituyen literalmente donde aparezcan.
2. Patrones genéricos ``clave=valor`` / ``Bearer xxx`` y parámetros sensibles en URLs.

La redacción por patrones es heurística: reduce el riesgo, pero la regla principal es no
pasar secretos a los mensajes de log en primer lugar.
"""

from __future__ import annotations

import re
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MASK = "***"

_SENSITIVE_KEYS = (
    r"(?:password|passwd|pwd|contrase(?:n|ñ)a|clave|token|secret|api[_-]?key|access[_-]?key"
    r"|session(?:id)?|authorization|cookie|sig|signature|csrf(?:_token)?)"
)
_KV_PATTERN = re.compile(rf"(?i)\b({_SENSITIVE_KEYS})\b(\s*[=:]\s*)([^\s&,;\"']+)")
_BEARER_PATTERN = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}")
_KEY_ONLY = re.compile(rf"(?i)^{_SENSITIVE_KEYS}$")


class SecretRegistry:
    """Conjunto de valores secretos conocidos en tiempo de ejecución (nunca se persiste)."""

    def __init__(self) -> None:
        self._values: set[str] = set()
        self._lock = threading.Lock()

    def register(self, value: str | None) -> None:
        if value and len(value) >= 3:
            with self._lock:
                self._values.add(value)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def values(self) -> list[str]:
        with self._lock:
            return sorted(self._values, key=len, reverse=True)


SECRETS = SecretRegistry()


def redact(text: object) -> str:
    """Devuelve ``text`` como cadena con secretos conocidos y patrones sensibles enmascarados."""
    if text is None:
        return ""
    result = str(text)
    for value in SECRETS.values():
        result = result.replace(value, MASK)
    result = _BEARER_PATTERN.sub(lambda m: f"{m.group(1)} {MASK}", result)
    result = _KV_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", result)
    return result


def redact_url(url: str) -> str:
    """Enmascara parámetros de consulta sensibles (``token``, ``key``...) de una URL."""
    if not url:
        return ""
    parts = urlsplit(url)
    if parts.query:
        query = [
            (key, MASK if _KEY_ONLY.match(key) else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        parts = parts._replace(query=urlencode(query, safe="*"))
    if parts.password:
        netloc = parts.netloc.replace(parts.password, MASK)
        parts = parts._replace(netloc=netloc)
    return redact(urlunsplit(parts))
