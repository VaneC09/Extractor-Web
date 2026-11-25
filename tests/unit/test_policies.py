"""Alcance, barreras, robots.txt, límites/cancelación y redacción de secretos."""

import logging
import time

import pytest

from web_extractor.core.barriers import detect_barrier
from web_extractor.core.errors import Cancelled, LimitReached, RobotsDisallowed, ScopeError
from web_extractor.core.limits import Budget, CancelToken, LimitValues, RateLimiter
from web_extractor.core.robots import RobotsPolicy
from web_extractor.core.scope import host_matches, validate_url
from web_extractor.utils.logging_utils import RedactingFilter
from web_extractor.utils.redaction import SECRETS, redact, redact_url

SCOPE = dict(allowed_schemes=["https"], allowed_domains=["*.example.org"], allowed_path_prefixes=["/datos/"],
             allow_private_network=False)


class TestScope:
    def test_accepts_in_scope(self):
        assert validate_url("https://www.example.org/datos/1", **SCOPE)

    @pytest.mark.parametrize("url, fragment", [
        ("http://www.example.org/datos/1", "Protocolo"),
        ("https://evil.com/datos/1", "Dominio"),
        ("https://example.org.evil.com/datos/", "Dominio"),
        ("https://www.example.org/admin", "Ruta"),
        ("https://user:pw@www.example.org/datos/", "credenciales"),
        ("ftp://www.example.org/datos/", "Protocolo"),
    ])
    def test_rejects(self, url, fragment):
        with pytest.raises(ScopeError, match=fragment):
            validate_url(url, **SCOPE)

    def test_private_network(self):
        scope = dict(SCOPE, allowed_domains=["127.0.0.1", "localhost"], allowed_schemes=["http"], allowed_path_prefixes=["/"])
        with pytest.raises(ScopeError, match="red local"):
            validate_url("http://127.0.0.1:8000/", **scope)
        assert validate_url("http://localhost:8000/", **dict(scope, allow_private_network=True))

    def test_wildcard(self):
        assert host_matches("a.b.example.org", ["*.example.org"])
        assert host_matches("example.org", ["*.example.org"])
        assert not host_matches("badexample.org", ["*.example.org"])


class TestBarriers:
    @pytest.mark.parametrize("status, kind", [(429, "rate_limit"), (503, "overload"), (401, "auth_required"),
                                              (403, "access_denied"), (402, "paywall")])
    def test_status_codes(self, status, kind):
        assert detect_barrier(status, {}, "").kind == kind

    @pytest.mark.parametrize("html, kind", [
        ('<div class="g-recaptcha" data-sitekey="x"></div>', "captcha"),
        ("<h1>Verifica que eres humano</h1>", "captcha"),
        ('<script src="https://hcaptcha.com/1/api.js"></script>', "captcha"),
        ("<title>Just a moment...</title><div id='cf-chl-widget'>", "bot_challenge"),
        ("<p>Suscríbete para continuar leyendo</p>", "paywall"),
        ('<form><input type="password" name="p"></form>', "auth_required"),
    ])
    def test_markers(self, html, kind):
        assert detect_barrier(200, {}, html).kind == kind

    def test_login_form_allowed_when_auth_expected(self):
        assert detect_barrier(200, {}, '<input type="password">', auth_expected=True) is None

    def test_normal_page(self):
        assert detect_barrier(200, {}, "<h1>Catálogo</h1><p>Productos</p>") is None

    def test_next_step_is_legitimate(self):
        step = detect_barrier(200, {}, "g-recaptcha").next_step
        assert "no resuelve ni evade" in step


class TestRobots:
    def test_disallow(self):
        policy = RobotsPolicy(lambda url: (200, "User-agent: *\nDisallow: /privado/\n"), "TestBot/1.0")
        assert policy.is_allowed("https://x.org/publico")
        with pytest.raises(RobotsDisallowed):
            policy.ensure_allowed("https://x.org/privado/a")

    def test_missing_robots_allows_and_server_error_disallows(self):
        assert RobotsPolicy(lambda url: (404, ""), "T").is_allowed("https://x.org/a")
        assert not RobotsPolicy(lambda url: (500, ""), "T").is_allowed("https://x.org/a")
        assert not RobotsPolicy(lambda url: (None, ""), "T").is_allowed("https://x.org/a")

    def test_crawl_delay_raises_delay(self):
        delays = []
        policy = RobotsPolicy(lambda url: (200, "User-agent: *\nCrawl-delay: 5\n"), "T", delays.append)
        policy.is_allowed("https://x.org/")
        assert delays == [5.0]

    def test_fetched_once_per_origin(self):
        calls = []
        policy = RobotsPolicy(lambda url: calls.append(url) or (200, ""), "T")
        for _ in range(3):
            policy.is_allowed("https://x.org/a")
        assert len(calls) == 1


class TestLimits:
    def limits(self, **kw):
        return LimitValues(**{"max_pages": 2, "max_records": 5, "max_requests": 3, "max_seconds": 10, **kw})

    def test_request_and_page_caps(self):
        budget = Budget(self.limits(), CancelToken())
        for _ in range(3):
            budget.consume_request()
        with pytest.raises(LimitReached, match="max_requests"):
            budget.consume_request()
        budget.consume_page()
        budget.consume_page()
        with pytest.raises(LimitReached, match="max_pages"):
            budget.consume_page()

    def test_time_cap(self):
        budget = Budget(self.limits(max_seconds=0.01), CancelToken())
        time.sleep(0.02)
        with pytest.raises(LimitReached, match="max_seconds"):
            budget.check()

    def test_cancel_interrupts_wait(self):
        token = CancelToken()
        token.cancel("prueba")
        start = time.monotonic()
        with pytest.raises(Cancelled):
            token.wait(5)
        assert time.monotonic() - start < 0.5

    def test_stop_file(self, tmp_path):
        stop = tmp_path / "STOP"
        token = CancelToken(stop)
        assert not token.cancelled
        stop.write_text("")
        assert token.cancelled and "STOP" in token.reason

    def test_rate_limiter_waits(self):
        limiter = RateLimiter(0.2, CancelToken())
        limiter.wait_turn()
        start = time.monotonic()
        limiter.wait_turn()
        assert time.monotonic() - start >= 0.18


class TestRedaction:
    def test_registered_secret(self):
        SECRETS.register("mi-clave-ultra")
        assert "mi-clave-ultra" not in redact("login con mi-clave-ultra")

    def test_patterns(self):
        assert redact("password=abc123 token: xyz") == "password=*** token: ***"
        assert "eyJhbGciOi" not in redact("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.x")

    def test_url_params(self):
        url = redact_url("https://x.org/a?page=2&api_key=SECRETO&token=T0K")
        assert "page=2" in url and "SECRETO" not in url and "T0K" not in url

    def test_logging_filter(self):
        SECRETS.register("valor-secreto")
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "usuario %s con %s", ("demo", "valor-secreto"), None)
        RedactingFilter().filter(record)
        assert "valor-secreto" not in record.getMessage()
