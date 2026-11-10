"""Validación de URLs contra el alcance autorizado.

Se aplica a la URL objetivo, a cada enlace de paginación, a cada redirección y a cada
navegación del navegador. Rechaza protocolos no HTTP(S), credenciales embebidas, dominios
o rutas fuera de alcance y, salvo autorización explícita (fixtures), destinos en red
privada/local para evitar accesos involuntarios a servicios internos.
"""

from __future__ import annotations

import ipaddress
import socket
from functools import lru_cache
from typing import Protocol, Sequence
from urllib.parse import urlsplit

from web_extractor.core.errors import ScopeError

SUPPORTED_SCHEMES = ("http", "https")


class ScopeLike(Protocol):
    allowed_schemes: Sequence[str]
    allowed_domains: Sequence[str]
    allowed_path_prefixes: Sequence[str]
    allow_private_network: bool


def host_matches(host: str, allowed_domains: Sequence[str]) -> bool:
    """``ejemplo.org`` coincide exacto; ``*.ejemplo.org`` admite el dominio y subdominios."""
    host = host.lower().rstrip(".")
    for allowed in allowed_domains:
        allowed = allowed.lower().rstrip(".")
        if allowed.startswith("*."):
            base = allowed[2:]
            if host == base or host.endswith("." + base):
                return True
        elif host == allowed:
            return True
    return False


def _ip_is_private(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


@lru_cache(maxsize=256)
def is_private_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return _ip_is_private(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return any(_ip_is_private(ipaddress.ip_address(info[4][0])) for info in infos)


def validate_url(
    url: str,
    *,
    allowed_schemes: Sequence[str],
    allowed_domains: Sequence[str],
    allowed_path_prefixes: Sequence[str],
    allow_private_network: bool,
) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ScopeError("URL vacía")
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in SUPPORTED_SCHEMES or scheme not in [s.lower() for s in allowed_schemes]:
        raise ScopeError(f"Protocolo no admitido por el alcance: '{scheme or '(ninguno)'}'")
    if not parts.hostname:
        raise ScopeError(f"La URL no tiene host: {url}")
    if parts.username or parts.password:
        raise ScopeError("No se admiten credenciales embebidas en la URL")
    if not host_matches(parts.hostname, allowed_domains):
        raise ScopeError(
            f"Dominio fuera de alcance: '{parts.hostname}' (permitidos: {', '.join(allowed_domains)})"
        )
    path = parts.path or "/"
    if not any(path.startswith(prefix) for prefix in allowed_path_prefixes):
        raise ScopeError(f"Ruta fuera de alcance: '{path}'")
    if not allow_private_network and is_private_host(parts.hostname):
        raise ScopeError(
            f"Destino en red local/privada no admitido: '{parts.hostname}'. "
            "Solo se permite con scope.allow_private_network=true (fixtures controlados)."
        )
    return url.strip()


def check_in_scope(url: str, scope: ScopeLike) -> str:
    return validate_url(
        url,
        allowed_schemes=scope.allowed_schemes,
        allowed_domains=scope.allowed_domains,
        allowed_path_prefixes=scope.allowed_path_prefixes,
        allow_private_network=scope.allow_private_network,
    )
