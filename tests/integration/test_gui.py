"""Interfaz gráfica: lógica pura, tarea en segundo plano y flujos con ``streamlit.testing``."""

from __future__ import annotations

import time

import pytest

from web_extractor.config.loader import parse_config
from web_extractor.config.templates import default_config_dict, fields_to_rows, rows_to_fields, slugify

from tests.conftest import ROOT

APP = str(ROOT / "web_extractor" / "gui" / "app.py")


def test_default_config_is_conservative():
    data = default_config_dict("https://datos.example.org/catalogo/2025?x=1")
    cfg = parse_config(data)
    assert not cfg.authorization.confirmed and cfg.authorization.environment == "production"
    assert cfg.scope.allowed_domains == ["datos.example.org"] and cfg.scope.allowed_path_prefixes == ["/catalogo/"]
    assert cfg.limits.delay_seconds >= 1 and cfg.extraction.method == "auto"
    assert default_config_dict("http://127.0.0.1:8765/")["authorization"]["environment"] == "fixture"
    assert slugify("Ñandú.org/ruta") == "nandu-org-ruta"


def test_field_rows_round_trip():
    fields = [
        {"name": "precio", "selector": ".price", "type": "float", "required": True,
         "normalize": ["strip", "parse_number"], "validate": {"min": 0, "max": 10, "regex": r"^\d"}},
        {"name": "estado", "column": "Estado", "validate": {"choices": ["A", "B"]}},
    ]
    back = rows_to_fields(fields_to_rows(fields) + [{"name": "  "}])
    assert back[0]["validate"] == {"regex": r"^\d", "min": 0.0, "max": 10.0}
    assert back[0]["normalize"] == ["strip", "parse_number"] and back[0]["required"] is True
    assert back[1]["validate"] == {"choices": ["A", "B"]} and back[1]["column"] == "Estado"
    assert len(back) == 2


def test_extraction_job_can_be_cancelled(example, server):
    from web_extractor.gui.jobs import ExtractionJob

    cfg = example("f01_catalogo_estatico.yaml", limits={"delay_seconds": 1.0})
    job = ExtractionJob(cfg).start()
    for _ in range(50):
        if job.counters()["solicitudes"] >= 1:
            break
        time.sleep(0.05)
    job.request_cancel()
    for _ in range(100):
        if not job.running:
            break
        time.sleep(0.05)
    assert not job.running and job.result is not None and job.result.status == "cancelado"


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _app():
    return streamlit_testing.AppTest.from_file(APP, default_timeout=60)


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def test_welcome_screen_renders():
    at = _app().run()
    assert not at.exception
    assert any("Empezar con una URL" in m.value for m in at.markdown)


def test_unknown_real_url_stays_locked(monkeypatch):
    at = _app().run()
    at.text_input(key="start_url").input("datos.example.org/catalogo")
    _button(at, "Comenzar").click().run()
    assert not at.exception
    assert at.session_state["w:target_url"] == "https://datos.example.org/catalogo"
    assert _button(at, "Ejecutar diagnóstico").disabled
    assert _button(at, "Vista previa en vivo").disabled
    assert not any(b.label == "Iniciar extracción" for b in at.button)
    texts = " ".join(w.value for w in at.warning)
    assert "authorized_by" in texts and "bloqueada" in texts

    at.text_input(key="w:authorization.authorized_by").input("Responsable de datos").run()
    assert _button(at, "Ejecutar diagnóstico").disabled  # falta el consentimiento para esta inspección
    at.checkbox(key="diag_consent").check().run()
    assert not _button(at, "Ejecutar diagnóstico").disabled
    assert _button(at, "Vista previa en vivo").disabled  # extraer sigue bloqueado


def _wait_job(at):
    job = at.session_state["job"]
    for _ in range(200):
        if not job.running:
            break
        time.sleep(0.1)
    at.run()
    return job


def test_unseen_site_flow_uses_suggested_rules_and_pagination(server):
    at = _app().run()
    at.text_input(key="start_url").input(f"{server.base_url}/nuevo/agenda")
    _button(at, "Comenzar").click().run()
    _button(at, "Ejecutar diagnóstico").click().run()
    _button(at, "Aplicar sugerencia a «Campos y reglas»").click().run()
    assert not at.exception
    assert at.session_state["w:extraction.pagination.mode"] == "url_template"
    assert at.session_state["w:extraction.record_selector"] == "div.evento"

    at.text_input(key="w:authorization.authorized_by").input("Equipo docente")
    at.text_area(key="w:authorization.purpose").input("Validar un sitio no incluido")
    at.checkbox(key="w:authorization.terms_reviewed").check()
    at.checkbox(key="w:authorization.confirmed").check().run()
    at.checkbox(key="run_confirm").check().run()
    _button(at, "Iniciar extracción").click().run()
    assert not at.exception
    job = _wait_job(at)
    assert job.result.status == "completado_con_limites" and job.result.quality.exported == 7


def test_full_flow_with_example(fixture_env, monkeypatch, tmp_path):
    monkeypatch.setenv("WE_GUI_FIXTURE_PORT", str(fixture_env.base_url.rsplit(":", 1)[1]))
    at = _app().run()
    option = next(o for o in at.selectbox(key="example_choice").options if o.startswith("f01"))
    at.selectbox(key="example_choice").select(option)
    _button(at, "Cargar ejemplo").click().run()
    assert not at.exception and not at.error

    _button(at, "Ejecutar diagnóstico").click().run()
    assert not at.exception
    assert at.session_state["diagnosis"].best.method == "static_html"

    _button(at, "Vista previa en vivo").click().run()
    assert at.session_state["preview"].records

    at.checkbox(key="run_confirm").check().run()
    _button(at, "Iniciar extracción").click().run()
    assert not at.exception
    assert at.session_state["run_confirm"] is False  # cada ejecución exige una confirmación nueva
    job = at.session_state["job"]
    for _ in range(200):
        if not job.running:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert job.result.status == "completado" and job.result.quality.exported > 0
    assert any("completado" in s.value for s in at.success)
