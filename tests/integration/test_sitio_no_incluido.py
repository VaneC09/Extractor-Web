"""¿Qué pasa con un sitio que no es uno de los ejemplos?

Dos grupos de pruebas, ninguna toca Internet:

1. Un sitio local "no visto" (``/nuevo/agenda``) sin YAML de ejemplo: el flujo genérico
   (plantilla desde la URL → diagnóstico → sugerencia → vista previa → extracción) debe funcionar.
2. Una sesión HTTP simulada que imita respuestas típicas de sitios reales (sin autorización,
   redirección a ``www``, robots.txt ausente o caído, desafío anti-bot, Latin-1 sin charset).
"""

from __future__ import annotations

import socket

import pytest
import requests

from web_extractor.config.loader import parse_config
from web_extractor.config.templates import default_config_dict
from web_extractor.core import http_client, scope
from web_extractor.core.engine import ExtractionEngine
from web_extractor.core.errors import AuthorizationError
from web_extractor.core.http_client import detect_encoding
from web_extractor.core.limits import RateLimiter
from web_extractor.selection.suggest import suggest_extraction

from tests.conftest import EXAMPLES

AUTHORIZED = {"confirmed": True, "authorized_by": "Equipo docente (sitio local controlado)",
              "purpose": "Validar el flujo genérico", "terms_reviewed": True}


def _authorize(data: dict, **extra) -> dict:
    data["authorization"].update(AUTHORIZED, **extra)
    return data


# ------------------------------------------------------------ sitio local no visto
def test_no_example_config_targets_the_unseen_site():
    assert not any("/nuevo/" in p.read_text(encoding="utf-8") for p in EXAMPLES.glob("*.yaml"))


def test_generic_flow_on_unseen_site(server, tmp_path):
    data = default_config_dict(f"{server.base_url}/nuevo/agenda")
    data["output"]["directory"] = str(tmp_path)
    assert data["authorization"]["confirmed"] is False
    assert data["scope"]["allowed_domains"] == ["127.0.0.1"] and data["scope"]["allowed_path_prefixes"] == ["/nuevo/"]

    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    assert diagnosis.best.method == "static_html" and not diagnosis.stopped
    codes = {f.code for f in diagnosis.findings}
    assert "html.api_docs" not in codes  # el texto "datos abiertos" dentro de un registro no es documentación

    suggestion = suggest_extraction(diagnosis)
    assert suggestion["record_selector"] == "div.evento"
    assert [f["name"] for f in suggestion["fields"]][:2] == ["titulo", "fecha"]
    assert suggestion["pagination"]["mode"] == "url_template" and "pagina={page}" in suggestion["pagination"]["url_template"]

    data["extraction"] = suggestion
    with pytest.raises(AuthorizationError):  # sin autorización declarada no hay vista previa en vivo
        ExtractionEngine(parse_config(data)).preview()
    cfg = parse_config(_authorize(data))
    preview = ExtractionEngine(cfg).preview(max_records=3)
    assert [r.data["lugar"] for r in preview.records] == ["Biblioteca Ñuñoa", "Auditorio José Martí",
                                                           "Sala Gabriela Mistral"]

    before = len(server.hits)
    result = ExtractionEngine(cfg).run(confirmed=True)
    assert result.status == "completado_con_limites" and "max_pages" in result.status_message
    assert result.quality.exported == 7 and result.quality.invalid == 0
    assert len(server.hits) - before <= cfg.limits.max_requests


def test_unseen_site_redirect_to_other_host_is_not_followed(server):
    data = default_config_dict(f"{server.base_url}/nuevo/redirige")
    before = len(server.hits)
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    assert diagnosis.stopped and diagnosis.incidents[0].kind == "out_of_scope"
    assert "redirige a http://localhost" in diagnosis.incidents[0].message
    assert not any("/nuevo/agenda" in h for h in server.hits[before:])


def test_unseen_site_bot_challenge_stops_without_retry(server):
    data = default_config_dict(f"{server.base_url}/nuevo/desafio")
    data["limits"]["max_retries"] = 3
    before = len(server.hits)
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    assert diagnosis.stopped and diagnosis.incidents[0].kind in ("bot_challenge", "captcha", "access_denied")
    assert diagnosis.incidents[0].next_step
    assert server.hits[before:].count("GET /nuevo/desafio") == 1


# ---------------------------------------------- sitios "reales" con sesión simulada
class FakeResponse:
    def __init__(self, status: int, body: bytes = b"", headers: dict | None = None) -> None:
        self.status_code = status
        self.headers = requests.structures.CaseInsensitiveDict(headers or {})
        self._body = body

    def iter_content(self, chunk_size: int = 65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self) -> None:
        pass


class FakeSite:
    """Sesión ``requests`` simulada: responde por URL exacta y anota cada solicitud."""

    def __init__(self, routes: dict[str, FakeResponse]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self):
        site = self

        class Session:
            headers: dict = {}

            def request(self, method, url, **kwargs):
                site.calls.append(f"{method} {url}")
                return site.routes.get(url, FakeResponse(404, b"<h1>404</h1>", {"Content-Type": "text/html"}))

            def close(self):
                pass

        return Session()


@pytest.fixture
def fake_site(monkeypatch):
    def install(routes: dict[str, FakeResponse]) -> FakeSite:
        site = FakeSite(routes)
        monkeypatch.setattr(http_client.requests, "Session", site)
        return site

    public_ip = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 0))]
    monkeypatch.setattr(scope.socket, "getaddrinfo", lambda *a, **k: public_ip)
    scope.is_private_host.cache_clear()
    monkeypatch.setattr(RateLimiter, "wait_turn", lambda self: None)  # la pausa se prueba aparte
    yield install
    scope.is_private_host.cache_clear()


HTML_OK = FakeResponse(200, '<html><body><h1>Datos públicos</h1><p>Texto suficiente para inspección.</p>'
                            '</body></html>'.encode(), {"Content-Type": "text/html; charset=utf-8"})
ROBOTS_OK = FakeResponse(200, b"User-agent: *\nAllow: /\n", {"Content-Type": "text/plain"})


def test_real_url_without_authorization_makes_zero_requests(fake_site, tmp_path):
    site = fake_site({"https://datos.example.org/catalogo": HTML_OK})
    data = default_config_dict("https://datos.example.org/catalogo")
    data["output"]["directory"] = str(tmp_path)
    cfg = parse_config(data)
    assert cfg.authorization.environment == "production" and cfg.limits.delay_seconds >= 1
    engine = ExtractionEngine(cfg)
    for action in (engine.diagnose, engine.preview, lambda: engine.run(confirmed=True)):
        with pytest.raises(AuthorizationError):
            action()
    assert site.calls == []


def test_real_url_with_declared_permission_only_diagnoses(fake_site):
    site = fake_site({"https://datos.example.org/robots.txt": ROBOTS_OK, "https://datos.example.org/catalogo": HTML_OK})
    data = default_config_dict("https://datos.example.org/catalogo")
    data["authorization"]["authorized_by"] = "Responsable de datos (correo del 2026-11-10)"
    engine = ExtractionEngine(parse_config(data))
    diagnosis = engine.diagnose()
    assert diagnosis.status_code == 200 and len(site.calls) == 2 <= data["diagnosis"]["max_requests"]
    with pytest.raises(AuthorizationError) as exc:
        engine.run(confirmed=True)
    assert any("evidence_reference" in m for m in exc.value.missing)
    assert len(site.calls) == 2


def test_redirect_to_www_is_reported_with_next_step(fake_site):
    site = fake_site({
        "https://example.org/robots.txt": FakeResponse(301, headers={"Location": "https://www.example.org/robots.txt"}),
        "https://example.org/": FakeResponse(301, headers={"Location": "https://www.example.org/"}),
    })
    data = _authorize(default_config_dict("https://example.org/"))
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    assert diagnosis.stopped
    incident = diagnosis.incidents[0]
    assert incident.kind == "robots_disallow" and "www" in incident.message
    assert not any("www.example.org" in c for c in site.calls)


def test_robots_404_allows_and_500_blocks(fake_site):
    site = fake_site({"https://a.example.org/robots.txt": FakeResponse(404), "https://a.example.org/": HTML_OK})
    data = _authorize(default_config_dict("https://a.example.org/"))
    assert not ExtractionEngine(parse_config(data)).diagnose().stopped

    site = fake_site({"https://b.example.org/robots.txt": FakeResponse(500), "https://b.example.org/": HTML_OK})
    data = _authorize(default_config_dict("https://b.example.org/"))
    data["limits"]["max_retries"] = 0
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    assert diagnosis.stopped and diagnosis.incidents[0].kind == "robots_disallow"
    assert "estado 500" in diagnosis.incidents[0].message
    assert site.calls == ["GET https://b.example.org/robots.txt"]


@pytest.mark.parametrize("status, body, kind", [
    (403, b"<title>Just a moment...</title><div class='cf-chl-x'>Checking your browser</div>", "bot_challenge"),
    (200, b"<div class='g-recaptcha'></div>", "captcha"),
    (429, b"Too many requests", "rate_limit"),
    (401, b"Login required", "auth_required"),
])
def test_real_site_barriers_stop_once(fake_site, status, body, kind):
    site = fake_site({"https://c.example.org/robots.txt": ROBOTS_OK,
                      "https://c.example.org/": FakeResponse(status, body, {"Content-Type": "text/html"})})
    data = _authorize(default_config_dict("https://c.example.org/"))
    data["limits"]["max_retries"] = 3
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    assert diagnosis.stopped and diagnosis.incidents[0].kind == kind
    assert site.calls.count("GET https://c.example.org/") == 1


def test_latin1_page_without_charset_header(fake_site):
    page = '<html><head><meta charset="ISO-8859-1"></head><body><p>Año, señal y acción pública.</p></body></html>'
    fake_site({"https://d.example.org/robots.txt": ROBOTS_OK,
               "https://d.example.org/": FakeResponse(200, page.encode("latin-1"), {"Content-Type": "text/html"})})
    data = _authorize(default_config_dict("https://d.example.org/"))
    diagnosis = ExtractionEngine(parse_config(data)).diagnose()
    summary = next(f for f in diagnosis.findings if f.code == "html.summary")
    assert "Año, señal y acción" in summary.evidence


def test_detect_encoding_rules():
    assert detect_encoding("text/html; charset=ISO-8859-1", b"") == "ISO-8859-1"
    assert detect_encoding("text/html", b'<meta charset="windows-1252">') == "windows-1252"
    assert detect_encoding("", "ñandú".encode()) == "utf-8"
    assert detect_encoding("", "ñandú".encode("latin-1")) == "windows-1252"
    assert detect_encoding("text/html; charset=inventado", b"abc") == "utf-8"
