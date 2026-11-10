"""CLI: códigos de salida y flujo guiado no interactivo."""

from pathlib import Path

from web_extractor.app import EXIT_AUTH, EXIT_CONFIG, EXIT_OK, EXIT_REVIEW, EXIT_STOPPED, main

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_validate(capsys):
    assert main(["validate", str(EXAMPLES / "f01_catalogo_estatico.yaml")]) == EXIT_OK
    assert main(["validate", str(EXAMPLES / "invalida_ejemplo.yaml")]) == EXIT_CONFIG
    assert "curp" in capsys.readouterr().out


def test_run_requires_confirmation_when_not_interactive(fixture_env, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = main(["run", str(EXAMPLES / "f02_tabla_html.yaml"), "--skip-diagnosis"])
    assert code == EXIT_AUTH and "no confirmada" in capsys.readouterr().out


def test_run_with_yes_completes(fixture_env, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["run", str(EXAMPLES / "f02_tabla_html.yaml"), "--yes"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Diagnóstico" in out and "Vista previa" in out and "completado" in out
    assert list((tmp_path / "outputs" / "f02-tabla-html").glob("*/data.csv"))


def test_run_stops_on_barrier(fixture_env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["run", str(EXAMPLES / "f09_barrera_captcha.yaml"), "--yes"]) == EXIT_STOPPED


def test_unauthorized_template_blocks_run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["run", str(EXAMPLES / "plantilla_sitio_autorizado.yaml"), "--yes"]) == EXIT_AUTH
    assert "No se realizará extracción" in capsys.readouterr().out


def test_preview_from_file_needs_no_authorization(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text((EXAMPLES / "plantilla_sitio_autorizado.yaml").read_text(encoding="utf-8")
                   .replace('"PLACEHOLDER .registro"', '"tbody tr"').replace('"PLACEHOLDER .titulo"', '"td"'), encoding="utf-8")
    fixture = EXAMPLES.parent / "fixtures" / "site" / "static" / "tabla.html"
    assert main(["preview", str(cfg), "--from-file", str(fixture)]) == EXIT_OK
    assert "Villa Aurora" in capsys.readouterr().out


def test_init_and_compare(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "nuevo.yaml"
    assert main(["init", "--url", "https://datos.example.org/tabla", "--out", str(out), "--non-interactive"]) == EXIT_OK
    assert "confirmed: false" in out.read_text()
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text('{"fields": {"x": {"fill_rate": 1.0}}, "record_count": 10}')
    b.write_text('{"fields": {"x": {"fill_rate": 0.0}}, "record_count": 10}')
    assert main(["compare-runs", str(a), str(b)]) == EXIT_REVIEW
    assert main(["compare-runs", str(a), str(a)]) == EXIT_OK
