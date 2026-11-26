"""Inicio de sesión en dos pantallas y código de verificación escrito por el titular (fixtures locales)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.conftest import requires_browser
from web_extractor.config.schema import AuthConfig
from web_extractor.core.auth import find_code_field
from web_extractor.core.engine import ExtractionEngine
from web_extractor.devtools.fixture_server import DEFAULT_PASSWORD
from web_extractor.gui.jobs import ExtractionJob

CODE = "codigo-739204"


@pytest.fixture(autouse=True)
def mfa_code(monkeypatch):
    monkeypatch.setenv("FIXTURE_MFA_CODE", CODE)


def two_step(example, fixture_env, prefix="/auth/pasos", file="f08_autenticacion_autorizada.yaml", **auth):
    return example(file, auth={"login_url": f"{fixture_env.base_url}{prefix}/login", "username_field": "email",
                               **auth})


def run(cfg, provider=None):
    return ExtractionEngine(cfg, code_provider=provider).run(confirmed=True)


def _no_secret_in_outputs(result, *secrets):
    for path in Path(result.run_dir).rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for secret in secrets:
                assert secret not in text, path.name


def test_email_then_password_in_separate_screens(example, fixture_env, hits):
    result = run(two_step(example, fixture_env))
    assert result.status == "completado" and result.quality.exported == 5
    assert len(hits("POST /auth/pasos/login")) == 1 and len(hits("POST /auth/pasos/password")) == 1
    _no_secret_in_outputs(result, DEFAULT_PASSWORD)


def test_unknown_email_stops_at_first_step(example, fixture_env, hits, monkeypatch):
    monkeypatch.setenv("WE_FIXTURE_USER", "otra-cuenta@example.org")
    result = run(two_step(example, fixture_env))
    assert result.status == "fallido" and result.incidents[0].kind == "auth_failed"
    assert len(hits("POST /auth/pasos/login")) == 1 and hits("POST /auth/pasos/password") == []


def test_verification_code_stops_when_nobody_can_type_it(example, fixture_env, hits):
    result = run(two_step(example, fixture_env, "/auth/pasos-codigo"), provider=lambda prompt: CODE)
    incident = result.incidents[0]
    assert incident.kind == "mfa_required" and "código" in incident.next_step
    assert hits("POST /auth/pasos-codigo/verificar") == [] and hits("/auth/privado") == []
    guide = Path(result.outputs["intervention"]).read_text(encoding="utf-8")
    assert "Pedirme el código de verificación" in guide and "no lee SMS" in guide


def test_verification_code_typed_by_account_owner(example, fixture_env, hits):
    prompts = []
    result = run(two_step(example, fixture_env, "/auth/pasos-codigo", ask_verification_code=True),
                 provider=lambda prompt: prompts.append(prompt) or CODE)
    assert result.status == "completado" and result.quality.exported == 5
    assert len(prompts) == 1 and len(hits("POST /auth/pasos-codigo/verificar")) == 1
    _no_secret_in_outputs(result, CODE, DEFAULT_PASSWORD)


def test_wrong_verification_code_is_not_retried(example, fixture_env, hits):
    result = run(two_step(example, fixture_env, "/auth/pasos-codigo", ask_verification_code=True),
                 provider=lambda prompt: "000000")
    assert result.status == "fallido" and result.incidents[0].kind == "auth_failed"
    assert len(hits("POST /auth/pasos-codigo/verificar")) == 1 and hits("/auth/privado") == []


def test_no_code_typed_in_time_stops(example, fixture_env, hits):
    result = run(two_step(example, fixture_env, "/auth/pasos-codigo", ask_verification_code=True), provider=lambda p: None)
    assert result.incidents[0].kind == "mfa_required" and hits("POST /auth/pasos-codigo/verificar") == []


def test_captcha_in_login_form_stops_over_http(example, fixture_env, hits):
    cfg = example("f08_autenticacion_autorizada.yaml", auth={
        "login_url": f"{fixture_env.base_url}/auth/con-captcha/login", "ask_verification_code": True})
    result = run(cfg, provider=lambda prompt: CODE)
    assert result.status == "detenido_barrera" and result.incidents[0].kind == "captcha"
    assert hits("POST /auth/con-captcha/login") == []


def test_login_that_redirects_to_home_outside_scope(example, fixture_env, hits):
    result = run(example("f08_autenticacion_autorizada.yaml",
                         auth={"login_url": f"{fixture_env.base_url}/auth/moodle/login"}))
    assert result.status == "completado" and result.quality.exported == 5
    assert len(hits("POST /auth/moodle/login")) == 1 and "GET /" not in hits()


@requires_browser
def test_browser_login_that_redirects_to_home_outside_scope(example, fixture_env, hits):
    result = run(example("f12_navegador_autenticado.yaml",
                         auth={"login_url": f"{fixture_env.base_url}/auth/moodle/login"}))
    assert result.status == "completado" and result.quality.exported == 5


def test_gui_job_waits_for_the_code(example, fixture_env):
    job = ExtractionJob(two_step(example, fixture_env, "/auth/pasos-codigo", ask_verification_code=True)).start()
    deadline = time.monotonic() + 30
    while job.code_request is None and job.running and time.monotonic() < deadline:
        time.sleep(0.05)
    assert job.code_request and "código de verificación" in job.code_request
    job.provide_code(CODE)
    while job.running and time.monotonic() < deadline:
        time.sleep(0.05)
    assert job.result.status == "completado" and job.result.quality.exported == 5


def test_postal_code_in_normal_form_is_not_a_verification_code():
    auth = AuthConfig()
    checkout = """<form><input name="nombre"><input name="calle"><input name="codigo_postal">
                  <input name="verificacion_correo"></form>"""
    assert find_code_field(checkout, auth) is None
    assert find_code_field('<form><input name="otp"><button>OK</button></form>', auth) == "otp"
    assert find_code_field('<form><input name="x1" autocomplete="one-time-code"></form>', auth) == "x1"


@requires_browser
def test_browser_two_step_login_with_code(example, fixture_env, hits):
    prompts = []
    cfg = two_step(example, fixture_env, "/auth/pasos-codigo", file="f12_navegador_autenticado.yaml",
                   ask_verification_code=True)
    result = run(cfg, provider=lambda prompt: prompts.append(prompt) or CODE)
    assert result.status == "completado" and result.quality.exported == 5
    assert len(prompts) == 1
    assert len(hits("POST /auth/pasos-codigo/login")) == 1 and len(hits("POST /auth/pasos-codigo/verificar")) == 1
    _no_secret_in_outputs(result, CODE, DEFAULT_PASSWORD)
