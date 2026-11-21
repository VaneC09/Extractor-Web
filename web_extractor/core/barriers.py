"""Detección heurística de barreras de acceso.

Objetivo: **detectar y detenerse**, nunca superar la barrera. La detección se basa en códigos
HTTP y marcadores textuales conocidos; puede tener falsos positivos (una página que menciona
"captcha") y falsos negativos (protecciones sin marcadores visibles). Por eso, ante la duda,
se prefiere detener el flujo y pedir revisión humana.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

NEXT_STEPS = {
    "captcha": "Solicitar al propietario del sitio una vía autorizada (API, exportación o permiso "
    "explícito). No resolver ni evadir el CAPTCHA.",
    "rate_limit": "Detener y reducir frecuencia; consultar con el propietario los límites admitidos "
    "antes de volver a intentar en otro momento.",
    "overload": "Detener: el servidor indica sobrecarga o mantenimiento. Reintentar más tarde solo con "
    "autorización y límites más conservadores.",
    "access_denied": "Detener: acceso denegado. Confirmar con el propietario si el recurso está "
    "autorizado para esta finalidad.",
    "auth_required": "Detener: se requiere autenticación. Solo continuar si existe autorización "
    "expresa y credenciales proporcionadas por el usuario (auth.type=form).",
    "paywall": "Detener: contenido de pago o suscripción. No eludir; obtener licencia o acceso "
    "autorizado.",
    "bot_challenge": "Detener: desafío anti-bot detectado. No evadir; usar una API o descarga oficial "
    "documentada por el propietario, o solicitar acceso autorizado.",
    "tls_error": "Detener: el certificado TLS no es válido para este dominio. No se desactiva la verificación; "
    "usar la dirección oficial con certificado válido (p. ej. la variante con o sin 'www', si el propietario "
    "la publica) o avisar al propietario.",
}

_CAPTCHA = re.compile(
    r"g-recaptcha|grecaptcha|recaptcha/api|h-captcha|hcaptcha\.com|cf-turnstile|"
    r"\bcaptcha\b|verify (?:that )?you are (?:a )?human|verifica que eres humano|"
    r"no soy un robot|i'?m not a robot|are you a robot",
    re.I,
)
_BOT_CHALLENGE = re.compile(
    r"cf-browser-verification|cf-chl-|_cf_chl_opt|/cdn-cgi/challenge-platform/|<title>just a moment\.\.\.</title>|"
    r"checking your browser|attention required!|"
    r"unusual traffic from your computer|tráfico inusual|access to this page has been denied",
    re.I,
)
_PAYWALL = re.compile(
    r"subscribe to (?:continue|read)|suscr[ií]bete para (?:continuar|leer)|paywall|"
    r"contenido exclusivo para suscriptores",
    re.I,
)
_PASSWORD_INPUT = re.compile(r"<input[^>]+type\s*=\s*[\"']?password", re.I)

_SCAN_LIMIT = 300_000


@dataclass
class Barrier:
    kind: str
    message: str
    evidence: str = ""
    status_code: int | None = None
    url: str = ""

    @property
    def next_step(self) -> str:
        return NEXT_STEPS.get(self.kind, "Detener y solicitar revisión humana.")


def _snippet(text: str, match: re.Match[str]) -> str:
    start = max(0, match.start() - 40)
    return " ".join(text[start : match.end() + 40].split())


_LINK = re.compile(r"<a\s[^>]*href", re.I)
OPTIONAL_LOGIN_MIN_LINKS = 40


def _content_beyond_login(html: str) -> bool:
    """Un recuadro de acceso opcional en una página con mucho contenido no es un muro de acceso.

    Un muro de acceso deja poco más que el formulario; una portada pública con un acceso para
    suscriptores conserva su navegación y su contenido (decenas de enlaces).
    """
    return len(_LINK.findall(html)) >= OPTIONAL_LOGIN_MIN_LINKS


def detect_barrier(
    status: int | None,
    headers: Mapping[str, str] | None,
    text: str,
    *,
    auth_expected: bool = False,
) -> Barrier | None:
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    if status == 429:
        retry = headers.get("retry-after", "")
        return Barrier("rate_limit", "HTTP 429: límite de solicitudes", f"Retry-After={retry}", status)
    if status == 503:
        return Barrier("overload", "HTTP 503: servicio no disponible o sobrecargado", "", status)
    if status in (401, 407):
        return Barrier("auth_required", f"HTTP {status}: autenticación requerida", "", status)
    if status == 402:
        return Barrier("paywall", "HTTP 402: pago requerido", "", status)
    if status == 403:
        sample = text[:_SCAN_LIMIT]
        if match := _CAPTCHA.search(sample):
            return Barrier("captcha", "HTTP 403 con CAPTCHA", _snippet(sample, match), status)
        if match := _BOT_CHALLENGE.search(sample):
            return Barrier("bot_challenge", "HTTP 403 con desafío anti-bot", _snippet(sample, match), status)
        return Barrier("access_denied", "HTTP 403: acceso denegado", "", status)

    sample = text[:_SCAN_LIMIT] if text else ""
    if match := _CAPTCHA.search(sample):
        return Barrier("captcha", "Indicios de CAPTCHA en la página", _snippet(sample, match), status)
    if match := _BOT_CHALLENGE.search(sample):
        return Barrier("bot_challenge", "Indicios de desafío anti-bot", _snippet(sample, match), status)
    if match := _PAYWALL.search(sample):
        return Barrier("paywall", "Indicios de muro de pago", _snippet(sample, match), status)
    if not auth_expected and (match := _PASSWORD_INPUT.search(sample)) and not _content_beyond_login(sample):
        return Barrier(
            "auth_required",
            "Formulario de acceso con contraseña en una página que debía ser pública",
            _snippet(sample, match),
            status,
        )
    return None
