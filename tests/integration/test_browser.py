"""Integración con Selenium (Chrome headless) contra fixtures locales. Se omite sin navegador."""

import pytest

from tests.conftest import requires_browser
from web_extractor.core.engine import ExtractionEngine
from web_extractor.extractors import browser_selenium

pytestmark = requires_browser


def run(cfg):
    return ExtractionEngine(cfg).run(confirmed=True)


def test_js_rendered_content(example):
    result = run(example("f03_js_renderizado.yaml"))
    assert result.status == "completado" and result.quality.exported == 5
    assert result.records[0].data["enlace"].endswith("/js/render.html#N-001")
    assert result.records[0].lineage["method"] == "browser"


def test_static_method_on_js_page_finds_nothing(example):
    cfg = example("f03_js_renderizado.yaml", extraction={"method": "static_html", "browser": {"wait_selector": None}})
    result = run(cfg)
    assert result.quality.exported == 0 and any(i.kind == "empty_page" for i in result.incidents)


def test_load_more_respects_max_clicks(example):
    result = run(example("f04_cargar_mas.yaml"))
    assert result.status == "completado_con_limites"
    assert result.budget["clicks"] == 2 and result.quality.exported == 12


def test_load_more_stops_when_records_are_enough(example):
    result = run(example("f04_cargar_mas.yaml", limits={"max_records": 4}))
    assert result.budget["clicks"] == 0 and result.quality.exported == 4


def test_infinite_scroll_respects_max_scrolls(example):
    result = run(example("f05_scroll_infinito.yaml"))
    assert result.status == "completado_con_limites"
    assert result.budget["scrolls"] == 2 and result.quality.exported == 15


def test_browser_detects_captcha_and_closes(example, monkeypatch):
    sessions = []
    original = browser_selenium.SeleniumSession.__init__

    def tracking_init(self, ctx):
        original(self, ctx)
        sessions.append(self)

    monkeypatch.setattr(browser_selenium.SeleniumSession, "__init__", tracking_init)
    base = example("f09_barrera_captcha.yaml")
    result = run(example("f09_barrera_captcha.yaml", extraction={"method": "browser"}))
    assert base.extraction.method == "static_html"
    assert result.status == "detenido_barrera" and result.incidents[0].kind == "captcha"
    assert sessions and all(s.driver is None for s in sessions)


def test_render_comparison_in_diagnosis(example):
    diagnosis = ExtractionEngine(example("f03_js_renderizado.yaml")).diagnose(render=True)
    codes = {f.code for f in diagnosis.findings}
    assert "render.adds_content" in codes and diagnosis.best.method == "browser"
    assert diagnosis.candidates["rendered_record_selectors"][0]["selector"].startswith("article")
