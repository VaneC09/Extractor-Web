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


def _labels(at):
    return [b.label for b in at.button]


def _authorize(at, evidence=False):
    at.selectbox(key="w:authorization.authorized_by").select("Docente o institución académica")
    at.selectbox(key="w:authorization.purpose").select("Uso educativo (proyecto académico)")
    if evidence:
        at.selectbox(key="w:authorization.evidence_reference").select("Creative Commons CC BY 4.0")
    at.checkbox(key="w:authorization.confirmed").check().run()


def test_welcome_screen_renders():
    at = _app().run()
    assert not at.exception
    assert any("¿Qué sitio quiere analizar?" in m.value for m in at.markdown)
    assert not at.sidebar.selectbox  # sin barra lateral para el usuario
    assert not any("ficticio" in c.value or "pruebas local" in c.value for c in at.caption)


def test_unknown_real_url_stays_locked_until_authorized():
    at = _app().run()
    at.text_input(key="start_url").input("datos.example.org/catalogo")
    _button(at, "Comenzar").click().run()
    assert not at.exception
    assert at.session_state["w:target_url"] == "https://datos.example.org/catalogo"
    assert "Diagnosticar sitio" not in _labels(at) and "Iniciar extracción" not in _labels(at)
    assert any("quién autoriza" in c.value for c in at.caption)

    at.selectbox(key="w:authorization.authorized_by").select("Propietario del sitio").run()
    assert "Diagnosticar sitio" not in _labels(at)  # faltan finalidad, permiso y confirmación
    _authorize(at, evidence=True)
    assert "Diagnosticar sitio" in _labels(at)
    assert at.session_state["w:authorization.confirmed"] is True


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
    _authorize(at)
    _button(at, "Diagnosticar sitio").click().run()
    assert not at.exception
    assert at.session_state["w:extraction.method"] == "static_html"  # la sugerencia se aplica sola
    assert at.session_state["w:extraction.pagination.mode"] == "url_template"
    assert at.session_state["w:extraction.record_selector"] == "div.evento"
    assert any("Tecnologías y mecanismos detectados" in m.value for m in at.markdown)

    _button(at, "Vista previa").click().run()
    assert at.session_state["preview"].records
    _button(at, "Iniciar extracción").click().run()
    assert not at.exception
    job = _wait_job(at)
    assert job.result.status == "completado_con_limites" and job.result.quality.exported == 7
    assert any("Resultados" in m.value for m in at.markdown)

    _button(at, "Analizar otra URL").click().run()
    at.text_input(key="start_url").input(f"{server.base_url}/nuevo/agenda")
    _button(at, "Comenzar").click().run()
    assert not at.exception
    assert any("Sitio ya analizado" in i.value for i in at.info)
    assert at.session_state["w:extraction.record_selector"] == "div.evento"
    assert at.session_state["w:authorization.confirmed"] is False
    kept = at.session_state["fields_rows"]
    at.checkbox(key="w:authorization.confirmed").check().run()
    _button(at, "Diagnosticar sitio").click().run()
    assert not at.exception
    assert at.session_state["fields_rows"] == kept  # el diagnóstico no pisa los campos recuperados


def test_unchecked_fields_are_not_extracted(server):
    at = _app().run()
    at.text_input(key="start_url").input(f"{server.base_url}/nuevo/agenda")
    _button(at, "Comenzar").click().run()
    _authorize(at)
    _button(at, "Diagnosticar sitio").click().run()
    import pandas as pd

    from web_extractor.gui import app as gui

    rows = at.session_state["fields_rows"]
    frame = pd.DataFrame([{"usar": i == 0, **r} for i, r in enumerate(rows)])
    names = [f["name"] for f in gui.rows_to_fields([{k: v for k, v in r.items() if k != "usar"}
                                                    for r in frame.to_dict(orient="records") if r["usar"]])]
    assert names == [rows[0]["name"]]


def test_full_flow_with_example(fixture_env, monkeypatch):
    monkeypatch.setenv("WE_GUI_EXAMPLES_DIR", str(ROOT / "examples"))
    at = _app().run()
    option = next(o for o in at.selectbox(key="example_choice").options if o.startswith("f01"))
    at.selectbox(key="example_choice").select(option)
    _button(at, "Cargar").click().run()
    assert not at.exception and not at.error

    _button(at, "Diagnosticar sitio").click().run()
    assert not at.exception
    assert at.session_state["diagnosis"].best.method == "static_html"

    _button(at, "Vista previa").click().run()
    assert at.session_state["preview"].records

    _button(at, "Iniciar extracción").click().run()
    assert not at.exception
    job = _wait_job(at)
    assert not at.exception
    assert job.result.status == "completado" and job.result.quality.exported > 0
    assert any("completado" in s.value for s in at.success)


def test_token_example_round_trips_and_runs(fixture_env, monkeypatch):
    monkeypatch.setenv("WE_GUI_EXAMPLES_DIR", str(ROOT / "examples"))
    at = _app().run()
    option = next(o for o in at.selectbox(key="example_choice").options if o.startswith("f13"))
    at.selectbox(key="example_choice").select(option)
    _button(at, "Cargar").click().run()
    assert not at.exception and not at.error
    assert at.session_state["w:auth.type"] == "header"
    assert at.session_state["w:auth.token_env"] == "WE_FIXTURE_API_TOKEN"

    _button(at, "Diagnosticar sitio").click().run()
    assert not at.exception
    assert any("WE_FIXTURE_API_TOKEN" in c.value and "definida" in c.value for c in at.caption)
    _button(at, "Iniciar extracción").click().run()
    job = _wait_job(at)
    assert not at.exception
    assert job.result.status == "completado" and job.result.quality.exported == 6
    assert any(job.result.run_id in c.value for c in at.caption)


def test_captcha_stops_the_flow_with_next_step(fixture_env, monkeypatch):
    monkeypatch.setenv("WE_GUI_EXAMPLES_DIR", str(ROOT / "examples"))
    at = _app().run()
    option = next(o for o in at.selectbox(key="example_choice").options if o.startswith("f09"))
    at.selectbox(key="example_choice").select(option)
    _button(at, "Cargar").click().run()
    _button(at, "Diagnosticar sitio").click().run()
    assert not at.exception
    assert any("Barrera detectada: captcha" in e.value and "Siguiente paso legítimo" in e.value
               and "¿Se puede continuar?" in e.value and "intervenciones.jsonl" in e.value for e in at.error)
    assert "Iniciar extracción" not in _labels(at) and "Vista previa" not in _labels(at)
