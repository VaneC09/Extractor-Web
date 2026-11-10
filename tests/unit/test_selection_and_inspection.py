"""Selección de campos e inspección sobre fixtures guardados (sin red)."""

from pathlib import Path

import pytest

from web_extractor.config.loader import parse_config
from web_extractor.config.schema import ExtractionConfig, FieldRule
from web_extractor.devtools.fixture_server import catalog_page
from web_extractor.inspectors.base import run_inspectors
from web_extractor.inspectors.classifier import classify
from web_extractor.models.results import Diagnosis, FetchedDocument
from web_extractor.reports.profiles import compare_profiles, requires_review
from web_extractor.selection.field_extractor import parse_document
from web_extractor.selection.paths import get_path, key_paths
from web_extractor.selection.suggest import suggest_extraction

SITE = Path(__file__).resolve().parents[2] / "fixtures" / "site"
CFG = parse_config({
    "project": {"name": "unit"}, "target_url": "http://localhost/x",
    "scope": {"allowed_domains": ["localhost"], "allowed_schemes": ["http"], "allow_private_network": True},
    "limits": {"delay_seconds": 0}, "extraction": {"method": "auto", "record_selector": "x", "fields": [{"name": "a"}]},
})


def doc(text, content_type="text/html", url="http://localhost/x"):
    return FetchedDocument(url, url, 200, content_type, text)


def test_html_records_with_attributes_and_relative_urls():
    extraction = ExtractionConfig(method="static_html", record_selector="article.product", fields=[
        FieldRule(name="sku", attribute="data-sku"), FieldRule(name="nombre", selector=".product-name"),
        FieldRule(name="url", selector="a.detail", attribute="href"), FieldRule(name="falta", selector=".nope")])
    result = parse_document(doc(catalog_page(1), url="http://localhost:1/static/catalogo?page=1"), extraction)
    assert len(result.items) == 4
    first = result.items[0]
    assert first["sku"] == "SKU-001" and first["nombre"] == "Cuaderno reciclado A5"
    assert first["url"] == "http://localhost:1/static/producto/SKU-001" and first["falta"] is None
    assert "h2.product-name" in result.structure


def test_html_table_by_column_name():
    extraction = ExtractionConfig(method="static_html", table_selector="table#indicadores", fields=[
        FieldRule(name="m", column="municipio"), FieldRule(name="t", column="Tasa de empleo (%)")])
    result = parse_document(doc((SITE / "static/tabla.html").read_text()), extraction)
    assert len(result.items) == 6 and result.items[0] == {"m": "Villa Aurora", "t": "61.2 %"}
    assert "column:Población" in result.structure


def test_json_and_csv():
    extraction = ExtractionConfig(method="api", records_path="data", fields=[
        FieldRule(name="n", path="name"), FieldRule(name="p", path="price.amount")])
    result = parse_document(doc('{"data":[{"name":"x","price":{"amount":2}}]}', "application/json"), extraction)
    assert result.items == [{"n": "x", "p": 2}] and "price.amount" in result.structure
    extraction = ExtractionConfig(method="structured_file", file_format="csv", fields=[FieldRule(name="i", path="id_estacion")])
    result = parse_document(doc((SITE / "files/estaciones.csv").read_text(), "text/csv"), extraction)
    assert len(result.items) == 6 and result.items[0]["i"] == "EST-01"


def test_paths():
    data = {"a": {"b": [{"c": 1}]}}
    assert get_path(data, "a.b.0.c") == 1 and get_path(data, "a.x") is None
    assert key_paths({"a": {"b": 1}, "c": 2}) == ["a", "a.b", "c"]


def inspect(text, content_type="text/html"):
    out = run_inspectors(doc(text, content_type))
    return out, {f.code for f in out.findings}, classify(out.findings, CFG)


def test_js_rendered_page_recommends_browser():
    out, codes, recs = inspect((SITE / "js/render.html").read_text())
    assert {"js.empty_root", "js.noscript"} <= codes
    assert recs[0].method == "browser"
    assert all(r.score <= 0.95 for r in recs)


def test_static_catalog_recommends_static_and_detects_pagination():
    out, codes, recs = inspect(catalog_page(1))
    assert {"html.pagination", "html.repeated", "html.text_present"} <= codes
    assert recs[0].method == "static_html"
    assert out.candidates["record_selectors"][0]["selector"] == "article.product"


def test_on_demand_and_scroll_hints():
    _, codes, _ = inspect((SITE / "js/load-more.html").read_text())
    assert "js.empty_root" in codes
    _, codes, recs = inspect((SITE / "js/scroll.html").read_text())
    assert "html.infinite_scroll" in codes and recs[0].method == "browser"


def test_structured_sources():
    _, codes, recs = inspect((SITE / "files/estaciones.csv").read_text(), "text/csv")
    assert "csv.columns" in codes and recs[0].method == "structured_file"
    _, codes, _ = inspect((SITE / "files/index.html").read_text())
    assert "html.data_files" in codes
    _, codes, recs = inspect((SITE / "api/docs.html").read_text())
    assert "html.api_docs" in codes
    api = next(r for r in recs if r.method == "api")
    assert api.executable is False and "no ejecutar" in api.requirements[0]


def test_suggestions_for_table_and_records():
    out = run_inspectors(doc((SITE / "static/tabla.html").read_text()))
    suggestion = suggest_extraction(Diagnosis("x", findings=out.findings, candidates=out.candidates,
                                              recommendations=classify(out.findings, CFG)))
    assert suggestion["table_selector"] == "table#indicadores"
    assert [f["column"] for f in suggestion["fields"]][:2] == ["Municipio", "Año"]
    out = run_inspectors(doc(catalog_page(1)))
    suggestion = suggest_extraction(Diagnosis("x", candidates=out.candidates))
    assert suggestion["record_selector"] == "article.product"
    assert any(f.get("attribute") == "href" for f in suggestion["fields"])


@pytest.mark.parametrize("change, severity", [
    ({"fields": {"a": {"fill_rate": 0.1, "selector": ".a"}}}, "alta"),
    ({"record_count": 0}, "alta"),
    ({"record_count": 4}, "media"),
    ({"structure": ["x"]}, "alta"),
])
def test_profile_changes(change, severity):
    base = {"method": "m", "fields": {"a": {"fill_rate": 1.0, "selector": ".a"}}, "record_count": 10,
            "structure": ["x", "y", "z"]}
    changes = compare_profiles(base, {**base, **change})
    assert any(c["severity"] == severity for c in changes)
    assert requires_review(changes) == (severity == "alta")
    assert compare_profiles(base, dict(base)) == []
