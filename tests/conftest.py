"""Fixtures de pytest: servidor local, carga de ejemplos con ajustes validados y limpieza de secretos."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest

from web_extractor.config.loader import load_config, parse_config
from web_extractor.devtools.fixture_server import DEFAULT_API_TOKEN, DEFAULT_PASSWORD, DEFAULT_USER, FixtureServer
from web_extractor.utils.redaction import SECRETS

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SITE = ROOT / "fixtures" / "site"


def browser_available() -> bool:
    try:
        import selenium  # noqa: F401
    except ImportError:
        return False
    return any(shutil.which(b) for b in ("google-chrome", "chromium", "chromium-browser", "chrome"))


requires_browser = pytest.mark.skipif(not browser_available(), reason="Chrome/Selenium no disponibles")


def deep_update(base: dict, updates: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result


@pytest.fixture(scope="session")
def server():
    with FixtureServer() as srv:
        yield srv


@pytest.fixture(autouse=True)
def _clear_secrets():
    SECRETS.clear()
    yield
    SECRETS.clear()


@pytest.fixture
def fixture_env(server, monkeypatch):
    monkeypatch.setenv("FIXTURE_BASE_URL", server.base_url)
    monkeypatch.setenv("WE_FIXTURE_USER", DEFAULT_USER)
    monkeypatch.setenv("WE_FIXTURE_PASSWORD", DEFAULT_PASSWORD)
    monkeypatch.setenv("WE_FIXTURE_API_TOKEN", DEFAULT_API_TOKEN)
    return server


@pytest.fixture
def example(fixture_env, tmp_path):
    """Carga un ejemplo, aplica cambios y vuelve a validar el resultado completo."""

    def _load(name: str, **updates):
        cfg = load_config(EXAMPLES / name)
        data = cfg.model_dump(by_alias=True, mode="json")
        data = deep_update(data, {"output": {"directory": str(tmp_path / "out")}, "limits": {"delay_seconds": 0.05}})
        data = deep_update(data, updates)
        return parse_config(data)

    return _load


@pytest.fixture
def hits(server):
    """Devuelve una función que cuenta solicitudes recibidas por el servidor desde ahora."""
    start = len(server.hits)

    def _count(fragment: str = "") -> list[str]:
        return [h for h in server.hits[start:] if fragment in h]

    return _count
