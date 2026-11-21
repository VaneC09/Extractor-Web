"""Capacidades añadidas para el reto final: XML, Excel, indicios de diagnóstico, barreras y procedencia."""

from __future__ import annotations

import pandas as pd
import pytest

from web_extractor.config.schema import ExtractionConfig, FieldRule
from web_extractor.core.barriers import detect_barrier
from web_extractor.extractors.browser_selenium import available_browsers
from web_extractor.inspectors.base import run_inspectors
from web_extractor.models.results import Diagnosis, FetchedDocument, ProcessedRecord, RawRecord
from web_extractor.selection.field_extractor import parse_document
from web_extractor.selection.suggest import suggest_extraction
from web_extractor.selection.xml_data import xml_to_data
from web_extractor.storage.exporters import ExcelExporter, ExportBundle
from web_extractor.transforms.pipeline import TransformPipeline

WB_XML = """<?xml version="1.0" encoding="utf-8"?>
<wb:data page="1" pages="1" per_page="50" total="2" xmlns:wb="http://www.worldbank.org">
  <wb:data><wb:indicator id="NY.GDP.MKTP.CD">GDP (current US$)</wb:indicator>
    <wb:country id="MX">México</wb:country><wb:date>2024</wb:date><wb:value>1852723000000</wb:value></wb:data>
  <wb:data><wb:indicator id="NY.GDP.MKTP.CD">GDP (current US$)</wb:indicator>
    <wb:country id="CA">Canada</wb:country><wb:date>2024</wb:date><wb:value/></wb:data>
</wb:data>"""


def _doc(text: str, content_type: str = "text/html", **headers) -> FetchedDocument:
    return FetchedDocument("https://datos.example.org/", "https://datos.example.org/", 200, content_type, text,
                           headers=headers)


# ------------------------------------------------------------------------- XML
def test_xml_to_data_strips_namespaces_and_keeps_attributes():
    data = xml_to_data(WB_XML)
    assert data["@total"] == "2" and len(data["data"]) == 2
    assert data["data"][0]["country"] == {"@id": "MX", "text": "México"} and data["data"][1]["value"] is None


def test_xml_records_use_the_same_paths_as_json():
    extraction = ExtractionConfig(method="structured_file", file_format="xml", records_path="data", fields=[
        FieldRule(name="pais", path="country.text"), FieldRule(name="codigo", path="country.@id"),
        FieldRule(name="valor", path="value")])
    result = parse_document(_doc(WB_XML, "application/xml"), extraction)
    assert result.items == [{"pais": "México", "codigo": "MX", "valor": "1852723000000"},
                            {"pais": "Canada", "codigo": "CA", "valor": None}]


def test_xml_response_is_inspected_and_suggested_as_structured_file():
    output = run_inspectors(_doc(WB_XML, "application/xml; charset=utf-8"))
    codes = {f.code for f in output.findings}
    assert {"response.xml", "json.records"} <= codes and output.candidates["data_format"] == "xml"
    diagnosis = Diagnosis(target_url="https://datos.example.org/", candidates=output.candidates)
    suggestion = suggest_extraction(diagnosis)
    assert suggestion["method"] == "structured_file" and suggestion["file_format"] == "xml"
    assert suggestion["records_path"] == "data" and "country.@id" in [f["path"] for f in suggestion["fields"]]


# ------------------------------------------------------------------------ Excel
def test_excel_export_has_data_and_incident_sheets(tmp_path):
    record = ProcessedRecord({"nombre": "Ñandú"}, {}, {"record_id": "1", "run_id": "r", "source_url": "https://x.org",
                                                       "validation_status": "valido", "validation_errors": []})
    path = ExcelExporter().export(ExportBundle("r", "p", ["nombre"], [record]), tmp_path)
    sheets = pd.read_excel(path, sheet_name=None)
    assert set(sheets) == {"datos", "incidencias"}
    assert sheets["datos"].loc[0, "nombre"] == "Ñandú" and sheets["datos"].loc[0, "_source_url"] == "https://x.org"


# ---------------------------------------------------------- indicios del diagnóstico
def _codes(html: str, **headers) -> set[str]:
    return {f.code for f in run_inspectors(_doc(html, **headers)).findings}


def test_thin_dom_with_scripts_points_to_javascript_loading():
    html = "<html><body><div id='contenido'></div>" + "<script src='/a.js'></script>" * 4 + "</body></html>"
    assert "js.thin_dom" in _codes(html)


def test_graphql_interaction_and_time_dependence_are_reported():
    html = ("<html><body><script>fetch('/graphql', {method: 'POST'})</script>"
            "<button aria-expanded='false'>Ver detalle</button><div role='tab'>Pestaña</div>"
            + "".join(f"<a href='/edicion?fecha=0{d}/11/2026'>Edición {d}</a>" for d in range(1, 5))
            + "<p>" + "texto " * 80 + "</p></body></html>")
    codes = _codes(html, **{"Last-Modified": "Thu, 19 Nov 2026 08:00:00 GMT"})
    assert {"api.graphql", "dom.interaction", "time.dependent"} <= codes


def test_last_modified_alone_is_not_time_dependent():
    assert "time.dependent" not in _codes("<html><body><p>" + "texto " * 80 + "</p></body></html>",
                                          **{"Last-Modified": "Thu, 19 Nov 2026 08:00:00 GMT"})


def test_navigation_menus_are_not_record_candidates():
    menu = "<nav><ul>" + "".join(f"<li class='nav-item'><a href='/s{i}'>Sección número {i}</a></li>" for i in range(8)) + "</ul></nav>"
    cards = "".join(f"<div class='ficha'><h3>Conjunto de datos {i}</h3><p class='desc'>Descripción {i} larga</p></div>"
                    for i in range(4))
    output = run_inspectors(_doc(f"<html><body>{menu}<main>{cards}</main></body></html>"))
    assert [c["selector"] for c in output.candidates["record_selectors"]] == ["div.ficha"]


def test_suggested_fields_are_values_not_layout_containers():
    cards = "".join(f"<li class='item'><div class='row'><div class='col'><h3 class='mb-2'><a href='/d{i}'>Datos {i}</a></h3>"
                    f"<p class='mb-2'>Actualización: 0{i}/11/2026</p></div></div></li>" for i in range(1, 5))
    output = run_inspectors(_doc(f"<html><body><ul>{cards}</ul></body></html>"))
    suggestion = suggest_extraction(Diagnosis(target_url="https://datos.example.org/", candidates=output.candidates))
    fields = {f["name"]: f["selector"] for f in suggestion["fields"]}
    assert fields["titulo"] == "h3.mb-2" and fields["mb_2"] == "p.mb-2" and "div.row" not in fields.values()


# ------------------------------------------------------------------- barreras
def test_optional_login_box_on_a_content_page_is_not_a_wall():
    links = "".join(f"<a href='/nota?id={i}'>Publicación {i}</a>" for i in range(60))
    page = f"<html><body><form><input type='password' name='clave'></form>{links}</body></html>"
    assert detect_barrier(200, {}, page) is None
    wall = "<html><body><h1>Acceso</h1><form><input type='password' name='clave'></form><a href='/'>Inicio</a></body></html>"
    assert detect_barrier(200, {}, wall).kind == "auth_required"


def test_captcha_still_stops_on_a_content_page():
    links = "".join(f"<a href='/n{i}'>n{i}</a>" for i in range(60))
    page = f"<html><body>{links}<script src='https://www.google.com/recaptcha/api.js'></script></body></html>"
    assert detect_barrier(200, {}, page).kind == "captcha"


# ---------------------------------------------------------- procedencia y navegador
def test_lineage_records_where_each_field_came_from():
    extraction = ExtractionConfig(method="static_html", record_selector="li", fields=[
        FieldRule(name="titulo", selector="h3 a"), FieldRule(name="url", selector="h3 a", attribute="href"),
        FieldRule(name="pais", path="country.@id")])
    raw = RawRecord({"titulo": "A", "url": "https://x.org", "pais": "MX"}, "https://x.org/lista", "2026-11-21T00:00:00Z",
                    "static_html", 0)
    records, _ = TransformPipeline(extraction).process([raw], "run-1")
    assert records[0].lineage["field_sources"] == {"titulo": "selector 'h3 a'", "url": "selector 'h3 a' @href",
                                                   "pais": "ruta 'country.@id'"}


def test_available_browsers_only_lists_supported_engines():
    assert set(available_browsers()) <= {"chrome", "edge"}


@pytest.mark.parametrize("engine", ["chrome", "edge", "auto"])
def test_browser_engine_is_configurable(engine):
    from web_extractor.config.schema import BrowserConfig

    assert BrowserConfig(engine=engine).engine == engine
