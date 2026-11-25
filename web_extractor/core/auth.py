"""Autenticación por formulario **solo** cuando está autorizada expresamente.

- Credenciales leídas de variables de entorno indicadas por nombre en la configuración.
- Los valores se registran en ``SECRETS`` para que se enmascaren en cualquier log.
- Se envían los campos ocultos del propio formulario (comportamiento normal de un navegador).
- Si el inicio de sesión falla, se detiene: no se reintenta ni se prueban otras credenciales.
- Si el formulario incluye CAPTCHA u otra barrera, se detiene.
- Formularios en una pantalla o en dos (primero usuario o correo y después contraseña).
- Código de verificación (2FA): solo si ``auth.ask_verification_code`` está activo, el titular de la
  cuenta lo escribe cuando se le pide; nunca se lee de SMS o correo ni se genera. Si no hay quien lo
  escriba, se detiene con la incidencia ``mfa_required``.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from web_extractor.config.schema import AuthConfig
from web_extractor.core.barriers import Barrier
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


_CODE_NAME = re.compile(r"otp|one[-_]?time|2fa|mfa|totp|c[oó]digo|code|verif", re.I)
_NOT_CODE = re.compile(r"postal|zip|promo|cup[oó]n|coupon|country|pa[ií]s|area", re.I)
_CODE_TYPES = {"text", "number", "tel", "password", ""}
_NOT_TYPED = {"hidden", "submit", "button", "checkbox", "radio", "image", "reset"}


def find_code_field(html: str, auth: AuthConfig) -> str | None:
    """Campo de un formulario corto que pide un código de verificación (2FA), si lo hay."""
    soup = BeautifulSoup(html, "html.parser")
    for inp in soup.find_all("input"):
        name = inp.get("name") or ""
        kind = (inp.get("type") or "").lower()
        if not name or kind not in _CODE_TYPES or name == auth.password_field:
            continue
        if auth.verification_code_field and name == auth.verification_code_field:
            return name
        one_time = (inp.get("autocomplete") or "").lower() == "one-time-code"
        if not one_time and (not _CODE_NAME.search(name) or _NOT_CODE.search(name)):
            continue
        form = inp.find_parent("form")
        typed = [i for i in (form.find_all("input") if form else [])
                 if (i.get("type") or "text").lower() not in _NOT_TYPED]
        if form is not None and len(typed) <= 2:
            return name
    return None


def request_code(client: PoliteHttpClient, auth: AuthConfig, url: str) -> str:
    """Pide al titular de la cuenta el código que recibió. Nunca se obtiene ni se genera automáticamente."""
    if not auth.ask_verification_code or client.code_provider is None:
        client.actions.record("login", url, "el sitio pide un código de verificación", "stop")
        raise BarrierDetected(Barrier("mfa_required", "El sitio pide un código de verificación (2FA)", "", None, url))
    client.actions.record("login", url, "esperando el código de verificación del titular de la cuenta", "ok")
    code = (client.code_provider("Escriba el código de verificación que recibió (SMS, correo o app)") or "").strip()
    if not code:
        client.actions.record("login", url, "no se recibió el código de verificación", "stop")
        raise BarrierDetected(Barrier("mfa_required", "No se escribió el código de verificación a tiempo", "", None, url))
    SECRETS.register(code)
    return code


def _form_with(soup: BeautifulSoup, field_name: str):
    field = soup.find("input", attrs={"name": field_name})
    return field.find_parent("form") if field else None


def _submit(client: PoliteHttpClient, page, form, values: dict[str, str], purpose: str):
    payload = {
        inp.get("name"): inp.get("value", "")
        for inp in form.find_all("input")
        if inp.get("name") and inp.get("type", "text").lower() == "hidden"
    }
    payload.update(values)
    action = urljoin(page.final_url, form.get("action") or page.final_url)
    try:
        return client.post_form(action, payload, purpose=purpose)
    except BarrierDetected as exc:
        if exc.barrier.kind != "auth_required":
            raise
        client.actions.record("login", action, f"credenciales rechazadas ({exc.barrier.message})", "stop")
        raise AuthFailed("El inicio de sesión autorizado fue rechazado; no se reintenta.") from None


def _rejected(result, auth: AuthConfig, field_name: str) -> bool:
    if result.status >= 400 or (auth.failure_text and auth.failure_text in result.text):
        return True
    return BeautifulSoup(result.text, "html.parser").find("input", attrs={"name": field_name}) is not None


def form_login(client: PoliteHttpClient, auth: AuthConfig) -> None:
    """Formulario de acceso en una o dos pantallas (usuario y luego contraseña) y código 2FA opcional."""
    assert auth.login_url
    username, password = read_credentials(auth)
    page = client.get(auth.login_url, purpose="formulario de acceso autorizado", auth_expected=True)
    soup = BeautifulSoup(page.text, "html.parser")
    form = _form_with(soup, auth.password_field)
    values = {auth.username_field: username, auth.password_field: password}
    if form is None:
        first = _form_with(soup, auth.username_field)
        if first is None:
            raise AuthFailed(f"No se encontró un formulario con el campo '{auth.username_field}' ni "
                             f"'{auth.password_field}'")
        page = _submit(client, page, first, {auth.username_field: username}, "envío del usuario (paso 1 de 2)")
        if _rejected(page, auth, auth.username_field) and _form_with(
                BeautifulSoup(page.text, "html.parser"), auth.password_field) is None:
            client.actions.record("login", page.final_url, "usuario rechazado en el paso 1", "stop")
            raise AuthFailed("El sitio rechazó el usuario en el primer paso; no se reintenta.")
        form = _form_with(BeautifulSoup(page.text, "html.parser"), auth.password_field)
        if form is None:
            raise AuthFailed("Tras enviar el usuario no apareció el campo de contraseña; no se reintenta.")
        values = {auth.password_field: password}
        client.actions.record("login", page.final_url, "paso 1 de 2 aceptado: se pide la contraseña", "ok")
    result = _submit(client, page, form, values, "envío de credenciales autorizadas")
    code_field = find_code_field(result.text, auth) if result.status < 400 else None
    if code_field:
        code = request_code(client, auth, result.final_url)
        code_form = _form_with(BeautifulSoup(result.text, "html.parser"), code_field)
        result = _submit(client, result, code_form, {code_field: code}, "envío del código de verificación")
        if _rejected(result, auth, code_field):
            client.actions.record("login", result.final_url, "código de verificación rechazado", "stop")
            raise AuthFailed("El código de verificación fue rechazado; no se reintenta.")
        client.actions.record("login", result.final_url, "código de verificación aceptado (valor oculto)", "ok")
    if _rejected(result, auth, auth.password_field):
        client.actions.record("login", result.final_url, "credenciales rechazadas", "stop")
        raise AuthFailed("El inicio de sesión autorizado fue rechazado; no se reintenta.")
    client.actions.record("login", result.final_url, "sesión iniciada", "ok")
