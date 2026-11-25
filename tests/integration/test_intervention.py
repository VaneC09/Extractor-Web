"""Intervención humana: pasos por barrera, dónde se registran y continuación con acceso autorizado."""

import json
from pathlib import Path

import pytest

from web_extractor.app import EXIT_OK, EXIT_STOPPED, main
from web_extractor.core.barriers import detect_barrier
from web_extractor.core.engine import ExtractionEngine
from web_extractor.models.results import Incident
from web_extractor.reports.intervention import (
    GENERAL_LOG,
    INTERVENTION_LOG,
    guide_for,
    intervention_entries,
    write_intervention,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_guides_say_when_extraction_can_continue():
    auth = guide_for("auth_required")
    assert auth["can_continue"] == "si_con_credenciales" and "token" in auth["answer"]
    steps = " ".join(auth["steps"])
    assert "Acceso autorizado" in steps and "$env:" in steps and "Escribirlos aquí" in steps
    assert "Nunca en la configuración" in steps
    assert guide_for("captcha")["can_continue"] == "con_persona_captcha"
    assert guide_for("access_denied")["can_continue"] == "no"
    assert "no lo envía a servicios de resolución" in guide_for("captcha")["steps"][0]
    assert guide_for("rate_limit")["can_continue"] == "mas_tarde"
    assert guide_for("limit") is None


def test_write_intervention_appends_to_central_log(tmp_path):
    incidents = [Incident("captcha", "CAPTCHA", "https://x.org/"), Incident("limit", "max_pages (2)")]
    entries = intervention_entries(incidents, stage="diagnóstico", project="p", target_url="https://x.org/")
    assert [e["kind"] for e in entries] == ["captcha"]
    files = write_intervention(entries, tmp_path / "p" / "a", tmp_path)
    write_intervention(entries, tmp_path / "p" / "b", tmp_path)
    assert "usted mismo lo resuelve" in Path(files["intervention"]).read_text(encoding="utf-8")
    lines = (tmp_path / INTERVENTION_LOG).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["file"] == files["intervention"]
    assert write_intervention([], tmp_path / "p" / "c", tmp_path) == {}


def test_captcha_diagnosis_records_steps_and_logs(example):
    cfg = example("f09_barrera_captcha.yaml")
    diagnosis = ExtractionEngine(cfg).diagnose()
    out = Path(cfg.output.directory)
    assert diagnosis.stopped
    for key in ("intervention", "actions", "markdown", "log"):
        assert Path(diagnosis.files[key]).exists(), key
    assert "¿Se puede continuar?" in Path(diagnosis.files["markdown"]).read_text(encoding="utf-8")
    central = [json.loads(line) for line in (out / INTERVENTION_LOG).read_text(encoding="utf-8").splitlines()]
    assert central[-1]["kind"] == "captcha" and central[-1]["stage"] == "diagnóstico"
    assert "INCIDENCIA captcha" in (out / GENERAL_LOG).read_text(encoding="utf-8")


@pytest.mark.parametrize("html", [
    '<div class="geetest_holder"></div><script src="https://static.geetest.com/static/js/gt.js"></script>',
    '<script src="https://client-api.arkoselabs.com/fc/api/"></script><div id="FunCaptcha"></div>',
    "<div>Desliza para completar el rompecabezas</div>",
    "<p>Slide to complete the puzzle</p>",
    "<p>Drag the puzzle piece into place</p>",
])
def test_puzzle_and_slider_captchas_are_detected(html):
    barrier = detect_barrier(200, {}, html)
    assert barrier is not None and barrier.kind == "captcha" and "rompecabezas" in barrier.message
    assert detect_barrier(403, {}, html).kind == "captcha"


def test_press_and_hold_is_a_captcha():
    assert detect_barrier(200, {}, "<p>Press &amp; Hold to confirm you are a human</p>").kind == "captcha"
    assert detect_barrier(200, {}, "<p>Mantén presionado el botón</p>").kind == "captcha"


def test_redirect_to_a_verification_wall_is_a_barrier():
    from web_extractor.core.barriers import barrier_from_redirect

    wall = barrier_from_redirect("https://www.tienda.example/captcha/wall/web-risk-verification?go_url=x")
    assert wall.kind == "captcha" and "verificación humana o CAPTCHA" in wall.message
    account = barrier_from_redirect("https://www.tienda.example/gz/account-verification?go=https%3A%2F%2Fx&tid=1")
    assert account.kind == "captcha"
    assert barrier_from_redirect("https://x.example/cdn-cgi/challenge-platform/h/b").kind == "bot_challenge"
    assert barrier_from_redirect("https://x.example/login?next=/datos").kind == "auth_required"
    assert barrier_from_redirect("https://x.example/login?next=/datos", auth_expected=True) is None
    assert barrier_from_redirect("https://x.example/catalogo/pagina-2") is None


def test_carousel_text_is_not_a_captcha():
    assert detect_barrier(200, {}, "<div class='carrusel'>Desliza para ver más productos</div>") is None


def test_puzzle_captcha_stops_run_and_records_steps(example, server):
    cfg = example("f09_barrera_captcha.yaml", target_url=f"{server.base_url}/barrier/captcha_rompecabezas.html")
    diagnosis = ExtractionEngine(cfg).diagnose()
    assert diagnosis.stopped and diagnosis.incidents[0].kind == "captcha"
    assert "rompecabezas" in Path(diagnosis.files["intervention"]).read_text(encoding="utf-8")
    result = ExtractionEngine(cfg).run(confirmed=True)
    assert result.status == "detenido_barrera" and not result.records
    steps = Path(result.outputs["intervention"]).read_text(encoding="utf-8")
    assert "usted mismo lo resuelve" in steps and "deslizador" in steps


def test_cli_run_continues_with_authorized_token(fixture_env, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["run", str(EXAMPLES / "f13_api_con_token.yaml"), "--yes"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "¿Se puede continuar? Sí" in out and "se continúa" in out and "completado" in out
    assert (tmp_path / "outputs" / INTERVENTION_LOG).exists()


def test_cli_barrier_prints_where_steps_are_recorded(fixture_env, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["run", str(EXAMPLES / "f09_barrera_captcha.yaml"), "--yes"]) == EXIT_STOPPED
    out = capsys.readouterr().out
    assert "Pasos de intervención humana:" in out and "intervencion_humana.md" in out
