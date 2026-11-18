"""Autenticación por formulario **solo** cuando está autorizada expresamente.

- Credenciales leídas de variables de entorno indicadas por nombre en la configuración.
- Los valores se registran en ``SECRETS`` para que se enmascaren en cualquier log.
- Se envían los campos ocultos del propio formulario (comportamiento normal de un navegador).
- Si el inicio de sesión falla, se detiene: no se reintenta ni se prueban otras credenciales.
- Si el formulario incluye CAPTCHA u otra barrera, se detiene.
"""

from __future__ import annotations

import os
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from web_extractor.config.schema import AuthConfig
from web_extractor.core.barriers import _PASSWORD_INPUT
from web_extractor.core.errors import AuthFailed, BarrierDetected
from web_extractor.core.http_client import PoliteHttpClient
from web_extractor.utils.redaction import SECRETS


def apply_header_auth(client: PoliteHttpClient, auth: AuthConfig) -> None:
    """Clave/token de una API documentada: se envía en un encabezado y se enmascara en toda salida."""
    token = os.environ.get(auth.token_env or "", "")
    if not token:
        raise AuthFailed(f"Falta el token en la variable de entorno {auth.token_env}. Defínala en su entorno; "
                         "nunca en el YAML.")
    SECRETS.register(token)
    client.auth_headers[auth.header_name] = f"{auth.header_prefix}{token}"
    client.actions.record("auth_header", "", f"encabezado {auth.header_name} configurado (valor oculto)")


def prepare_auth(client: PoliteHttpClient, auth: AuthConfig) -> None:
    if auth.type == "form":
        form_login(client, auth)
    elif auth.type == "header":
        apply_header_auth(client, auth)


def read_credentials(auth: AuthConfig) -> tuple[str, str]:
    username = os.environ.get(auth.username_env or "", "")
    password = os.environ.get(auth.password_env or "", "")
    if not username or not password:
        raise AuthFailed(
            f"Faltan credenciales en las variables de entorno {auth.username_env} / {auth.password_env}. "
            "Defínalas en su entorno; nunca en el YAML."
        )
    SECRETS.register(username)
    SECRETS.register(password)
    return username, password


def form_login(client: PoliteHttpClient, auth: AuthConfig) -> None:
    assert auth.login_url
    username, password = read_credentials(auth)
    page = client.get(auth.login_url, purpose="formulario de acceso autorizado", auth_expected=True)
    soup = BeautifulSoup(page.text, "html.parser")
    password_input = soup.find("input", attrs={"name": auth.password_field})
    form = password_input.find_parent("form") if password_input else None
    if form is None:
        raise AuthFailed(f"No se encontró un formulario con el campo '{auth.password_field}'")
    payload = {
        inp.get("name"): inp.get("value", "")
        for inp in form.find_all("input")
        if inp.get("name") and inp.get("type", "text").lower() == "hidden"
    }
    payload[auth.username_field] = username
    payload[auth.password_field] = password
    action = urljoin(page.final_url, form.get("action") or page.final_url)
    try:
        result = client.post_form(action, payload, purpose="envío de credenciales autorizadas")
    except BarrierDetected as exc:
        if exc.barrier.kind != "auth_required":
            raise
        client.actions.record("login", action, f"credenciales rechazadas ({exc.barrier.message})", "stop")
        raise AuthFailed("El inicio de sesión autorizado fue rechazado; no se reintenta.") from None
    failed = result.status >= 400 or bool(_PASSWORD_INPUT.search(result.text))
    if auth.failure_text and auth.failure_text in result.text:
        failed = True
    if failed:
        client.actions.record("login", action, "credenciales rechazadas", "stop")
        raise AuthFailed("El inicio de sesión autorizado fue rechazado; no se reintenta.")
    client.actions.record("login", action, "sesión iniciada", "ok")
