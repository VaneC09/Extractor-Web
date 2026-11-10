from pathlib import Path

import pytest

from web_extractor.config.loader import config_summary, load_config, parse_config
from web_extractor.core.authorization import missing_for_extraction
from web_extractor.core.errors import ConfigError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

MINIMAL = {
    "project": {"name": "demo"},
    "target_url": "https://datos.example.org/lista",
    "scope": {"allowed_domains": ["datos.example.org"]},
    "extraction": {"method": "static_html", "record_selector": ".item", "fields": [{"name": "titulo"}]},
}


def with_(**changes):
    data = {**MINIMAL}
    for key, value in changes.items():
        data[key] = value
    return data


@pytest.mark.parametrize("path", sorted(p.name for p in EXAMPLES.glob("*.yaml") if p.name != "invalida_ejemplo.yaml"))
def test_examples_are_valid(path):
    assert load_config(EXAMPLES / path).project.name


def test_invalid_example_lists_every_problem():
    with pytest.raises(ConfigError) as exc:
        load_config(EXAMPLES / "invalida_ejemplo.yaml")
    text = "\n".join(exc.value.messages)
    for expected in ("target_url", "password", "curp", "dinero", "quitar_todo", "project.name"):
        assert expected in text


def test_minimal_config_has_conservative_defaults():
    cfg = parse_config(MINIMAL)
    assert cfg.limits.delay_seconds >= 1.0
    assert cfg.limits.concurrency == 1
    assert cfg.authorization.confirmed is False
    assert cfg.scope.respect_robots_txt is True


@pytest.mark.parametrize("url", ["ftp://datos.example.org/x", "file:///etc/passwd", "javascript:alert(1)"])
def test_rejects_non_http_protocols(url):
    with pytest.raises(ConfigError):
        parse_config(with_(target_url=url))


def test_rejects_target_outside_scope():
    with pytest.raises(ConfigError, match="fuera"):
        parse_config(with_(target_url="https://otro.example.com/"))


def test_rejects_private_network_without_flag():
    data = with_(target_url="http://127.0.0.1:9/x", scope={"allowed_domains": ["127.0.0.1"], "allowed_schemes": ["http"]})
    with pytest.raises(ConfigError, match="red local"):
        parse_config(data)


def test_remote_requires_minimum_delay():
    with pytest.raises(ConfigError, match="delay_seconds"):
        parse_config(with_(limits={"delay_seconds": 0.2}))


def test_private_network_flag_forbidden_for_remote_domains():
    with pytest.raises(ConfigError, match="allow_private_network"):
        parse_config(with_(scope={"allowed_domains": ["datos.example.org"], "allow_private_network": True}))


def test_limits_have_upper_bounds():
    with pytest.raises(ConfigError, match="max_pages"):
        parse_config(with_(limits={"max_pages": 10_000}))


def test_auth_requires_explicit_authorization():
    auth = {"type": "form", "login_url": "https://datos.example.org/login", "username_env": "U", "password_env": "P"}
    with pytest.raises(ConfigError, match="allow_authentication"):
        parse_config(with_(auth=auth))


def test_literal_secrets_are_rejected_in_auth_block():
    auth = {"type": "form", "login_url": "https://datos.example.org/login", "username_env": "U",
            "password_env": "P", "password": "123"}
    with pytest.raises(ConfigError, match="password"):
        parse_config(with_(auth=auth, authorization={"allow_authentication": True}))


def test_env_expansion_only_for_allowed_names(monkeypatch):
    monkeypatch.setenv("WE_HOST", "datos.example.org")
    cfg = parse_config(with_(target_url="https://${WE_HOST}/lista"))
    assert cfg.target_url == "https://datos.example.org/lista"
    monkeypatch.setenv("WE_API_TOKEN", "abc123")
    with pytest.raises(ConfigError, match="no expandible"):
        parse_config(with_(target_url="https://datos.example.org/${WE_API_TOKEN}"))
    with pytest.raises(ConfigError, match="no expandible"):
        parse_config(with_(target_url="https://${HOME}/x"))


def test_method_specific_requirements():
    with pytest.raises(ConfigError, match="record_selector"):
        parse_config(with_(extraction={"method": "browser", "fields": [{"name": "a"}]}))
    with pytest.raises(ConfigError, match="file_format"):
        parse_config(with_(extraction={"method": "structured_file", "fields": [{"name": "a", "path": "a"}]}))
    with pytest.raises(ConfigError, match="path"):
        parse_config(with_(extraction={"method": "api", "fields": [{"name": "a"}]}))
    with pytest.raises(ConfigError, match="next_selector"):
        parse_config(with_(extraction={**MINIMAL["extraction"], "pagination": {"mode": "next_link"}}))
    with pytest.raises(ConfigError, match="method=browser"):
        parse_config(with_(extraction={**MINIMAL["extraction"], "browser": {"infinite_scroll": True}}))


def test_duplicate_fields_and_bad_regex():
    with pytest.raises(ConfigError, match="repetidos"):
        parse_config(with_(extraction={**MINIMAL["extraction"], "fields": [{"name": "a"}, {"name": "a"}]}))
    with pytest.raises(ConfigError, match="regular"):
        parse_config(with_(extraction={**MINIMAL["extraction"], "fields": [{"name": "a", "validate": {"regex": "("}}]}))


def test_missing_authorization_items_are_listed():
    missing = missing_for_extraction(parse_config(with_(authorization={"environment": "production"})))
    text = " ".join(missing)
    for key in ("confirmed", "authorized_by", "purpose", "terms_reviewed", "evidence_reference"):
        assert key in text


def test_summary_excludes_secret_values(monkeypatch):
    monkeypatch.setenv("WE_FIXTURE_PASSWORD", "super-secreto-1")
    cfg = load_config(EXAMPLES / "f08_autenticacion_autorizada.yaml")
    assert "super-secreto-1" not in str(config_summary(cfg))
    assert config_summary(cfg)["auth"]["password_env"] == "WE_FIXTURE_PASSWORD"
