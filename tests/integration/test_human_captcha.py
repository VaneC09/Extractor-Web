"""CAPTCHA resuelto por una persona en el navegador visible: la herramienta solo espera, nunca lo resuelve."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import requires_browser
from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.errors import BarrierDetected
from web_extractor.extractors import browser_selenium
from web_extractor.extractors.browser_selenium import SeleniumSession
from web_extractor.reports.intervention import guide_for

WALL = (Path(__file__).resolve().parents[2] / "fixtures" / "site" / "barrier" / "captcha.html").read_text(encoding="utf-8")
CONTENT = "<article>Aviso 1</article>"


class FakeDriver:
    """Página que muestra el CAPTCHA hasta que «la persona» lo completa tras ``solve_after`` consultas."""

    def __init__(self, base_url: str, solve_after: int | None, answered: bool = False) -> None:
        self.solve_after, self.answered, self.reads = solve_after, answered, 0
        self.current_url = f"{base_url}/barrier/captcha_persona.html"

    @property
    def page_source(self) -> str:
        self.reads += 1
        solved = self.solve_after is not None and self.reads > self.solve_after
        return CONTENT if solved else WALL

    def execute_script(self, script: str) -> bool:
        return self.answered


def session(example, fixture_env, solve_after, answered=False, human=True, notices=None):
    driver = FakeDriver(fixture_env.base_url, solve_after, answered)
    cfg = example("f09_barrera_captcha.yaml", extraction={"method": "browser", "browser": {"human_verification": human}})
    engine = ExtractionEngine(cfg, human_notice=notices.append if notices is not None else None)
    s = SeleniumSession(engine._context(engine._limit_values()))
    s.driver = driver
    return s


def test_without_option_captcha_stops(example, fixture_env):
    s = session(example, fixture_env, solve_after=None, human=False)
    with pytest.raises(BarrierDetected) as exc:
        s.check_barrier()
    assert exc.value.barrier.kind == "captcha"


def test_person_solves_captcha_and_flow_continues(example, fixture_env):
    notices = []
    s = session(example, fixture_env, solve_after=2, notices=notices)
    s.check_barrier()
    assert "Resuélvalo usted en la ventana del navegador" in notices[0]
    assert notices[-1] is None
    incident = s.ctx.incidents.items[0]
    assert incident.kind == "captcha" and incident.severity == "media" and "resuelto por una persona" in incident.message
    details = [e.detail for e in s.ctx.actions.entries if e.action == "human_verification"]
    assert details == ["captcha: esperando a una persona", "captcha: resuelto por una persona"]
    assert s.ctx.budget.paused > 0
    assert [e.target for e in s.ctx.actions.entries if e.action == "http_get"] == [f"{fixture_env.base_url}/robots.txt"]


def test_answered_widget_counts_as_solved(example, fixture_env):
    s = session(example, fixture_env, solve_after=None, answered=True)
    s.check_barrier()
    assert s.ctx.incidents.items[0].severity == "media"


def test_nobody_solves_it_in_time(example, fixture_env, monkeypatch):
    monkeypatch.setattr(browser_selenium, "HUMAN_TIMEOUT_SECONDS", 2)
    s = session(example, fixture_env, solve_after=None)
    with pytest.raises(BarrierDetected) as exc:
        s.check_barrier()
    assert "nadie lo resolvió" in exc.value.barrier.message


def test_repeated_captcha_stops_after_limit(example, fixture_env):
    s = session(example, fixture_env, solve_after=None)
    s.human_solved.update({"http://a/1", "http://a/2", "http://a/3"})
    with pytest.raises(BarrierDetected) as exc:
        s.check_barrier()
    assert "se repite" in exc.value.barrier.message


def test_guide_explains_person_must_solve_it():
    guide = guide_for("captcha")
    assert guide["can_continue"] == "con_persona_captcha"
    text = " ".join(guide["steps"])
    assert "no resuelve" in text and "Resolveré yo el CAPTCHA" in text and "no sustituye la autorización" in text


@requires_browser
def test_browser_waits_for_person_then_extracts(example, fixture_env):
    cfg = example("f09_barrera_captcha.yaml", target_url=f"{fixture_env.base_url}/barrier/captcha_persona.html",
                  extraction={"method": "browser", "browser": {"human_verification": True}})
    result = ExtractionEngine(cfg).run(confirmed=True)
    assert result.status == "completado" and result.quality.exported == 3
    assert result.incidents[0].kind == "captcha" and "resuelto por una persona" in result.incidents[0].message
