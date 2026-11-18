"""Cobertura explícita de la rúbrica: autenticación autorizada en todos los mecanismos y trazabilidad."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

import yaml

from tests.conftest import EXAMPLES, requires_browser
from web_extractor.config.loader import config_fingerprint, parse_config
from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.errors import ConfigError
from web_extractor.devtools.fixture_server import DEFAULT_API_TOKEN, DEFAULT_PASSWORD


def run(cfg):
    return ExtractionEngine(cfg).run(confirmed=True)


def _no_secret_in_outputs(result, secret: str) -> None:
    for path in Path(result.run_dir).iterdir():
        assert secret not in path.read_text(encoding="utf-8", errors="ignore"), path.name


# --------------------------------------------------------------- API con token
def test_api_with_token_header(example, hits):
    result = run(example("f13_api_con_token.yaml"))
    assert result.status == "completado" and result.quality.exported == 6
    assert result.records[0].data == {"codigo": "ART-01", "descripcion": "Artículo interno 1", "existencias": 7}
    _no_secret_in_outputs(result, DEFAULT_API_TOKEN)


def test_api_with_wrong_token_stops_once(example, hits, monkeypatch):
    monkeypatch.setenv("WE_FIXTURE_API_TOKEN", "token-equivocado")
    result = run(example("f13_api_con_token.yaml", limits={"max_retries": 3}))
    assert result.status == "detenido_barrera" and result.incidents[0].kind == "auth_required"
    assert len(hits("/api/v1/privado")) == 1
    _no_secret_in_outputs(result, "token-equivocado")


def test_api_token_missing_makes_no_api_request(example, hits, monkeypatch):
    monkeypatch.delenv("WE_FIXTURE_API_TOKEN")
    result = run(example("f13_api_con_token.yaml"))
    assert result.status == "fallido" and "WE_FIXTURE_API_TOKEN" in result.status_message
    assert hits("/api/v1/privado") == []


def test_token_is_never_sent_to_robots_txt(example, monkeypatch):
    sent: list[tuple[str, dict]] = []
    from web_extractor.core import http_client

    original = http_client.requests.Session.request

    def spy(self, method, url, headers=None, **kwargs):
        sent.append((url, dict(headers or {})))
        return original(self, method, url, headers=headers, **kwargs)

    monkeypatch.setattr(http_client.requests.Session, "request", spy)
    run(example("f13_api_con_token.yaml"))
    robots = [h for u, h in sent if u.endswith("/robots.txt")]
    api = [h for u, h in sent if "/api/v1/privado" in u]
    assert robots and all("Authorization" not in h for h in robots)
    assert api and all(h.get("Authorization") == f"Bearer {DEFAULT_API_TOKEN}" for h in api)


@pytest.mark.parametrize("change, message", [
    ({"extraction": {"method": "static_html", "record_selector": "div"}}, "solo aplica a APIs"),
    ({"auth": {"token_env": None}}, "requiere token_env"),
    ({"auth": {"header_name": "Cookie"}}, "no está permitido"),
    ({"authorization": {"allow_authentication": False}}, "allow_authentication"),
])
def test_header_auth_validation(example, change, message):
    with pytest.raises(ConfigError) as exc:
        example("f13_api_con_token.yaml", **change)
    assert message in str(exc.value)


# ------------------------------------------------------- navegador con sesión
@requires_browser
def test_browser_login_then_js_content(example, hits):
    result = run(example("f12_navegador_autenticado.yaml"))
    assert result.status == "completado" and result.quality.exported == 5
    assert result.records[0].lineage["method"] == "browser"
    assert len(hits("POST /auth/login")) == 1
    _no_secret_in_outputs(result, DEFAULT_PASSWORD)


@requires_browser
def test_browser_rejected_login_stops_without_retry(example, hits, monkeypatch):
    monkeypatch.setenv("WE_FIXTURE_PASSWORD", "contraseña-equivocada")
    result = run(example("f12_navegador_autenticado.yaml", limits={"max_retries": 3}))
    assert result.status == "fallido" and result.incidents[0].kind == "auth_failed"
    assert len(hits("POST /auth/login")) == 1 and hits("/auth/panel") == []
    _no_secret_in_outputs(result, "contraseña-equivocada")


@requires_browser
def test_browser_without_auth_hits_login_barrier(example, hits):
    result = run(example("f12_navegador_autenticado.yaml", auth={"type": "none"},
                         authorization={"allow_authentication": False}))
    assert result.status == "detenido_barrera" and result.incidents[0].kind == "auth_required"


# --------------------------------------------------------------- trazabilidad
def test_every_output_carries_provenance(example):
    cfg = example("f01_catalogo_estatico.yaml")
    result = run(cfg)
    effective = json.loads(Path(result.outputs["config"]).read_text(encoding="utf-8"))
    assert result.config_sha256 == config_fingerprint(effective) and len(result.config_sha256) == 64
    assert result.tool_version

    frame = pd.read_csv(result.outputs["csv"])
    assert set(frame["_config_sha256"]) == {result.config_sha256}
    assert frame["_retrieved_at"].notna().all() and set(frame["_method"]) == {"static_html"}

    document = json.loads(Path(result.outputs["json"]).read_text(encoding="utf-8"))
    assert document["metadata"]["config_sha256"] == result.config_sha256
    lineage = document["records"][0]["lineage"]
    for key in ("source_url", "retrieved_at", "method", "validation_status", "transformations", "run_id",
                "config_sha256", "tool_version"):
        assert lineage[key] not in (None, ""), key

    summary = json.loads(Path(result.outputs["summary"]).read_text(encoding="utf-8"))
    assert summary["config_sha256"] == result.config_sha256
    with sqlite3.connect(result.outputs["sqlite"]) as conn:
        row = conn.execute("SELECT config_sha256, tool_version FROM runs WHERE run_id = ?", (result.run_id,)).fetchone()
    assert row == (result.config_sha256, result.tool_version)
    assert f"`{result.config_sha256}`" in Path(result.outputs["report"]).read_text(encoding="utf-8")


def test_fingerprint_changes_only_with_configuration(example):
    a = example("f01_catalogo_estatico.yaml").model_dump(mode="json", by_alias=True)
    b = example("f01_catalogo_estatico.yaml").model_dump(mode="json", by_alias=True)
    c = example("f01_catalogo_estatico.yaml", limits={"max_pages": 2}).model_dump(mode="json", by_alias=True)
    assert config_fingerprint(a) == config_fingerprint(b) != config_fingerprint(c)


def test_sqlite_created_by_previous_version_is_migrated(tmp_path, example):
    db = tmp_path / "antigua.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, project TEXT NOT NULL, target_url TEXT, method TEXT, "
                     "status TEXT, started_at TEXT, finished_at TEXT, metadata_json TEXT)")
    cfg = example("f02_tabla_html.yaml", output={"sqlite_path": str(db)})
    result = run(cfg)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT config_sha256 FROM runs").fetchone() == (result.config_sha256,)


def test_browser_auth_config_is_accepted():
    raw = yaml.safe_load((EXAMPLES / "f12_navegador_autenticado.yaml").read_text(encoding="utf-8"))
    assert parse_config(raw).extraction.method == "browser"
