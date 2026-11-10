import pytest

from web_extractor.config.schema import ExtractionConfig, FieldRule
from web_extractor.models.results import RawRecord
from web_extractor.transforms.casting import CastError, cast_value
from web_extractor.transforms.normalizers import apply_normalizer
from web_extractor.transforms.pipeline import TransformPipeline, process_field


@pytest.mark.parametrize("name, value, expected", [
    ("collapse_whitespace", "  a   b \n c ", "a b c"),
    ("remove_currency", "$1,299.00 MXN", "1,299.00"),
    ("thousands_comma", "1,299.00", "1299.00"),
    ("decimal_comma", "1.234,50", "1234.50"),
    ("remove_percent", "61.2 %", "61.2"),
    ("empty_to_none", "N/D", None),
    ("digits_only", "Tel. 55-12", "5512"),
    ("strip_accents", "Educación", "Educacion"),
])
def test_normalizers(name, value, expected):
    assert apply_normalizer(name, value) == expected


def test_normalizers_ignore_non_strings():
    assert apply_normalizer("lower", 12) == 12


@pytest.mark.parametrize("value, type_, expected", [
    ("12", "integer", 12), (3.0, "integer", 3), ("1.5", "float", 1.5), (2, "float", 2.0),
    ("Disponible", "boolean", True), ("no", "boolean", False),
    ("2025-01-10", "date", "2025-01-10"), ("https://x.org/a", "url", "https://x.org/a"),
    ({"a": 1}, "string", '{"a": 1}'),
])
def test_cast(value, type_, expected):
    assert cast_value(value, type_) == expected


def test_cast_with_date_format():
    assert cast_value("15/01/2025", "date", "%d/%m/%Y") == "2025-01-15"


@pytest.mark.parametrize("value, type_", [("1,2", "integer"), ("abc", "float"), (True, "integer"),
                                          ("quizá", "boolean"), ("ayer", "date"), ("/relativa", "url")])
def test_cast_errors(value, type_):
    with pytest.raises(CastError):
        cast_value(value, type_)


def test_process_field_records_steps_and_errors():
    rule = FieldRule(name="precio", type="float", normalize=["remove_currency", "thousands_comma"],
                     validate={"min": 0, "max": 1000})
    value, steps, errors = process_field(rule, "$1,299.00 MXN")
    assert value is None and steps == ["remove_currency", "thousands_comma", "cast:float", "validate"]
    assert "máximo" in errors[0]
    value, _, errors = process_field(rule, "$45.50")
    assert value == 45.5 and errors == []


def test_pattern_extraction():
    rule = FieldRule(name="lugares", type="integer", pattern=r"(\d+)")
    assert process_field(rule, "27 lugares")[0] == 27
    value, _, errors = process_field(rule, "sin cupo")
    assert value is None and "patrón" in errors[0]


def make_extraction(**kw):
    fields = [FieldRule(name="id", required=True), FieldRule(name="precio", type="float")]
    return ExtractionConfig(method="static_html", record_selector=".x", fields=fields, **kw)


def raw(values, url="http://fixture/1"):
    return RawRecord(values, url, "2026-01-01T00:00:00Z", "static_html", 0)


def test_pipeline_status_dedup_and_lineage():
    records = [raw({"id": "A", "precio": "1.5"}), raw({"id": "A", "precio": "1.5"}),
               raw({"id": None, "precio": "2"}), raw({"id": "B", "precio": "caro"})]
    out, quality = TransformPipeline(make_extraction()).process(records, "run-1")
    assert [r.lineage["validation_status"] for r in out] == ["valido", "invalido", "advertencia"]
    assert quality.duplicates_removed == 1 and quality.exported == 3
    assert quality.fields["precio"].invalid == 1
    lineage = out[0].lineage
    assert lineage["run_id"] == "run-1" and lineage["source_url"] == "http://fixture/1"
    assert lineage["transformations"]["precio"] == ["cast:float"]
    assert out[2].raw == {"id": "B", "precio": "caro"}


def test_pipeline_dedup_on_key_and_drop_invalid():
    records = [raw({"id": "A", "precio": "1"}), raw({"id": "A", "precio": "2"}), raw({"id": None, "precio": "3"})]
    out, quality = TransformPipeline(make_extraction(deduplicate_on=["id"], drop_invalid=True)).process(records, "r")
    assert len(out) == 1 and quality.dropped_invalid == 1 and quality.duplicates_removed == 1


def test_keep_raw_false():
    out, _ = TransformPipeline(make_extraction(keep_raw=False)).process([raw({"id": "A"})], "r")
    assert out[0].raw == {}
