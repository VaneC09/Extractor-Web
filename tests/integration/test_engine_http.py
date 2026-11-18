"""Integración del motor con el servidor de fixtures local (sin navegador)."""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.errors import AuthorizationError
from web_extractor.core.limits import CancelToken
from web_extractor.devtools.fixture_server import DEFAULT_PASSWORD

SITE = Path(__file__).resolve().parents[2] / "fixtures" / "site"


def run(cfg, **kw):
    return ExtractionEngine(cfg, **kw).run(confirmed=True)


def test_static_pagination_end_to_end(example, hits):
    cfg = example("f01_catalogo_estatico.yaml")
    result = run(cfg)
    assert result.status == "completado"
    assert result.budget["pages"] == 3 and len(hits("/static/catalogo")) == 3
    assert result.quality.exported == 10 and result.quality.duplicates_removed == 1 and result.quality.invalid == 1

    frame = pd.read_csv(result.outputs["csv"])
    assert {"sku", "precio", "_record_id", "_run_id", "_source_url", "_retrieved_at", "_method",
            "_validation_status"} <= set(frame.columns)
    assert frame.loc[frame.sku == "SKU-003", "precio"].item() == 1299.0

    data = json.loads(Path(result.outputs["json"]).read_text())
    record = data["records"][0]
    assert record["raw"]["precio"] == "$45.50 MXN" and record["data"]["precio"] == 45.5
    assert record["lineage"]["transformations"]["precio"] == ["remove_currency", "thousands_comma", "empty_to_none", "cast:float"]

    with sqlite3.connect(result.outputs["sqlite"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM records WHERE run_id = ?", (result.run_id,)).fetchone()[0] == 10
        assert conn.execute("SELECT status FROM runs WHERE run_id = ?", (result.run_id,)).fetchone()[0] == "completado"
    report = Path(result.outputs["report"]).read_text()
    assert "Consumo frente a límites" in report and "Siguientes pasos" in report
    actions = [json.loads(line) for line in Path(result.outputs["actions"]).read_text().splitlines()]
    assert sum(a["action"] == "http_get" for a in actions) == 4


@pytest.mark.parametrize("limits, expected_pages, expected_records, limit_name", [
    ({"max_pages": 2}, 2, 8, "max_pages"),
    ({"max_records": 3}, 1, 3, "max_records"),
    ({"max_requests": 2}, 1, 4, "max_requests"),
])
def test_limits_are_enforced(example, hits, limits, expected_pages, expected_records, limit_name):
    result = run(example("f01_catalogo_estatico.yaml", limits=limits))
    assert result.status == "completado_con_limites" and limit_name in result.status_message
    assert len(hits("/static/catalogo")) == expected_pages
    assert result.quality.total_raw == expected_records


def test_table_extraction(example):
    result = run(example("f02_tabla_html.yaml"))
    rows = {r.data["municipio"]: r.data for r in result.records}
    assert rows["Puerto Ejemplo"]["tasa_empleo"] is None and rows["Puerto Ejemplo"]["poblacion"] == 45120
    assert rows["Villa Aurora"]["actualizado"] == "2025-01-15"
    assert result.quality.with_warnings == 2


def test_documented_api_with_next_links(example, hits):
    result = run(example("f06_api_documentada.yaml"))
    assert result.status == "completado" and result.quality.exported == 9
    assert len(hits("/api/v1/products")) == 3
    assert result.records[0].data == {"id": 1, "nombre": "Producto API 1", "precio": 13.25, "moneda": "MXN",
                                      "categoria": "arte", "activo": True}


def test_undocumented_api_is_not_executed(example, hits):
    cfg = example("f06_api_documentada.yaml", extraction={"api": {"documented": False, "documentation_url": None}})
    with pytest.raises(AuthorizationError, match="no ejecutar"):
        run(cfg)
    assert hits() == []


def test_structured_csv(example):
    result = run(example("f07_archivo_csv.yaml"))
    assert result.quality.exported == 5 and result.quality.duplicates_removed == 1
    est4 = next(r for r in result.records if r.data["id_estacion"] == "EST-04")
    assert est4.data["latitud"] is None and est4.raw["latitud"] == "abc"


def test_authorized_login_without_leaking_secrets(example, hits):
    result = run(example("f08_autenticacion_autorizada.yaml"))
    assert result.status == "completado" and result.quality.exported == 5
    assert len(hits("POST /auth/login")) == 1
    run_dir = Path(result.run_dir)
    for path in run_dir.iterdir():
        assert DEFAULT_PASSWORD not in path.read_text(encoding="utf-8", errors="ignore"), path.name


def test_authorized_login_for_structured_file(example, hits, fixture_env):
    file_url = f"{fixture_env.base_url}/auth/informes.csv"
    extraction = {"method": "structured_file", "file_format": "csv", "table_selector": None,
                  "fields": [{"name": "folio", "path": "Folio", "required": True}, {"name": "estado", "path": "Estado"}]}
    result = run(example("f08_autenticacion_autorizada.yaml", target_url=file_url, extraction=extraction))
    assert result.status == "completado" and result.quality.exported == 5
    assert len(hits("POST /auth/login")) == 1

    blocked = run(example("f08_autenticacion_autorizada.yaml", target_url=file_url, extraction=extraction,
                          auth={"type": "none"}, authorization={"allow_authentication": False}))
    assert blocked.status == "detenido_barrera" and blocked.incidents[0].kind == "auth_required"


def test_rejected_login_stops_without_retry(example, hits, monkeypatch):
    monkeypatch.setenv("WE_FIXTURE_PASSWORD", "contraseña-equivocada")
    result = run(example("f08_autenticacion_autorizada.yaml", limits={"max_retries": 3}))
    assert result.status == "fallido" and result.incidents[0].kind == "auth_failed"
    assert len(hits("POST /auth/login")) == 1
    assert "contraseña-equivocada" not in Path(result.outputs["log"]).read_text()


def test_missing_credentials(example, monkeypatch, hits):
    monkeypatch.delenv("WE_FIXTURE_PASSWORD")
    result = run(example("f08_autenticacion_autorizada.yaml"))
    assert result.status == "fallido" and "variables de entorno" in result.status_message
    assert hits("/auth/") == []


def test_protected_page_without_auth_is_a_barrier(example, hits):
    cfg = example("f08_autenticacion_autorizada.yaml", auth={"type": "none"}, authorization={"allow_authentication": False})
    result = run(cfg)
    assert result.status == "detenido_barrera" and result.incidents[0].kind == "auth_required"
    assert hits("POST") == []


@pytest.mark.parametrize("config, kind, path", [
    ("f09_barrera_captcha.yaml", "captcha", "/barrier/captcha.html"),
    ("f10_limite_tasa.yaml", "rate_limit", "/barrier/limite"),
])
def test_barriers_stop_without_retries(example, hits, config, kind, path):
    result = run(example(config, limits={"max_retries": 3}))
    assert result.status == "detenido_barrera"
    assert result.incidents[0].kind == kind and result.incidents[0].next_step
    assert len(hits(path)) == 1


def test_forbidden_403(example, hits):
    cfg = example("f10_limite_tasa.yaml", target_url=example("f10_limite_tasa.yaml").target_url.replace("limite", "prohibido"))
    result = run(cfg)
    assert result.incidents[0].kind == "access_denied" and len(hits("/barrier/prohibido")) == 1


def test_transient_502_is_retried_within_cap(example, hits, server):
    server.httpd.unstable_count = 0
    base = example("f09_barrera_captcha.yaml")
    cfg = example("f09_barrera_captcha.yaml", target_url=base.target_url.replace("captcha.html", "inestable"),
                  extraction={"record_selector": "article.product", "fields": [{"name": "texto", "selector": ".product-name"}]},
                  limits={"max_retries": 1})
    result = run(cfg)
    assert result.status == "completado" and result.quality.exported == 4
    assert len(hits("/barrier/inestable")) == 2


def test_transient_without_retries_fails(example, hits, server):
    server.httpd.unstable_count = 0
    base = example("f09_barrera_captcha.yaml")
    cfg = example("f09_barrera_captcha.yaml", target_url=base.target_url.replace("captcha.html", "inestable"),
                  limits={"max_retries": 0})
    result = run(cfg)
    assert result.status == "fallido" and "502" in result.status_message


def test_robots_disallow_prevents_request(example, hits):
    result = run(example("f11_robots_prohibido.yaml"))
    assert result.status == "detenido_politica" and hits("/privado/") == []


def test_out_of_scope_pagination_is_blocked(example, hits):
    base = example("f01_catalogo_estatico.yaml")
    template = base.target_url.split("/static/")[0] + "/api/v1/products?page={page}"
    result = run(example("f01_catalogo_estatico.yaml", extraction={"pagination": {"mode": "url_template", "url_template": template}}))
    assert result.status == "detenido_politica" and result.incidents[0].kind == "out_of_scope"
    assert hits("/api/") == []


def test_url_template_pagination_stops_at_404(example, hits):
    base = example("f01_catalogo_estatico.yaml")
    template = base.target_url.replace("page=1", "page={page}")
    result = run(example("f01_catalogo_estatico.yaml", extraction={"pagination": {"mode": "url_template", "url_template": template}}))
    assert result.status == "completado" and result.budget["pages"] == 4 and result.quality.exported == 10


def test_requires_confirmation(example, hits):
    with pytest.raises(AuthorizationError, match="confirmación"):
        ExtractionEngine(example("f01_catalogo_estatico.yaml")).run(confirmed=False)
    with pytest.raises(AuthorizationError, match="confirmed"):
        run(example("f01_catalogo_estatico.yaml", authorization={"confirmed": False}))
    assert hits() == []


def test_cancel_before_start_makes_no_requests(example, hits):
    token = CancelToken()
    token.cancel("prueba")
    result = run(example("f01_catalogo_estatico.yaml"), cancel=token)
    assert result.status == "cancelado" and hits() == []


def test_stop_file_cancels(example, hits, tmp_path):
    cfg = example("f01_catalogo_estatico.yaml")
    stop = Path(cfg.output.directory) / cfg.output.stop_file
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text("")
    result = run(cfg)
    assert result.status == "cancelado" and "STOP" in result.status_message and hits() == []


def test_change_detection_requires_review(example):
    first = run(example("f01_catalogo_estatico.yaml"))
    assert not first.requires_human_review
    broken = example("f01_catalogo_estatico.yaml")
    fields = [f.model_dump(by_alias=True) for f in broken.extraction.fields]
    for f in fields:
        if f["name"] == "precio":
            f["selector"] = ".precio-nuevo"
    second = run(example("f01_catalogo_estatico.yaml", extraction={"fields": fields}))
    assert second.requires_human_review
    assert any(c["kind"] == "fill_rate_drop" and c["severity"] == "alta" for c in second.profile_changes)
    profile = json.loads((Path(broken.output.directory) / "profiles" / "f01-catalogo-estatico.json").read_text())
    assert profile["run_id"] == first.run_id


def test_diagnosis_is_conservative_and_explained(example, hits):
    diagnosis = ExtractionEngine(example("f01_catalogo_estatico.yaml")).diagnose()
    assert diagnosis.requests_used <= 3 and len(hits("/static/")) == 1
    assert diagnosis.best.method == "static_html" and diagnosis.best.reasons
    assert any("heurística" in item for item in diagnosis.limitations)
    diagnosis = ExtractionEngine(example("f09_barrera_captcha.yaml")).diagnose()
    assert diagnosis.stopped and diagnosis.incidents[0].kind == "captcha" and not diagnosis.recommendations


def test_diagnosis_of_api_prefers_documented_api(example):
    diagnosis = ExtractionEngine(example("f06_api_documentada.yaml")).diagnose()
    assert diagnosis.best.method == "api"
    assert diagnosis.candidates["records_paths"][0]["path"] == "data"


def test_preview_live_uses_one_page_and_offline_uses_none(example, hits):
    engine = ExtractionEngine(example("f01_catalogo_estatico.yaml"))
    preview = engine.preview(max_records=3)
    assert len(preview.records) == 3 and len(hits("/static/catalogo")) == 1
    before = len(hits())
    offline = engine.preview(from_file=SITE / "static" / "tabla.html")
    assert offline.requests_used == 0 and len(hits()) == before
