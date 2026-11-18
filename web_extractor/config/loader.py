"""Carga YAML/JSON, expansión controlada de variables y mensajes de error legibles.

La expansión ``${VAR:-defecto}`` solo admite variables con prefijo ``WE_`` o ``FIXTURE_`` y que
no parezcan secretos, para que nunca se inyecten credenciales dentro del objeto de configuración
(que se resume en informes).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from web_extractor.config.schema import ProjectConfig
from web_extractor.core.errors import ConfigError

_ENV_REF = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")
_ALLOWED_ENV = re.compile(r"^(WE_|FIXTURE_)[A-Z0-9_]+$")
_SECRET_ENV = re.compile(r"(PASS|SECRET|TOKEN|KEY|CRED)", re.I)


def _expand(value: Any, errors: list[str]) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            if not _ALLOWED_ENV.match(name) or _SECRET_ENV.search(name):
                errors.append(f"variable no expandible en configuración: {name} (use WE_/FIXTURE_ y nunca secretos)")
                return match.group(0)
            return os.environ.get(name, default if default is not None else "")

        return _ENV_REF.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand(v, errors) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v, errors) for v in value]
    return value


def format_validation_error(exc: ValidationError) -> list[str]:
    messages = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(raíz)"
        msg = err["msg"].removeprefix("Value error, ")
        messages.append(f"{loc}: {msg}")
    return messages


def parse_config(data: Any) -> ProjectConfig:
    if not isinstance(data, dict):
        raise ConfigError(["el archivo debe contener un objeto/mapa en la raíz"])
    errors: list[str] = []
    expanded = _expand(data, errors)
    if errors:
        raise ConfigError(errors)
    try:
        return ProjectConfig.model_validate(expanded)
    except ValidationError as exc:
        raise ConfigError(format_validation_error(exc)) from None


def load_config(path: str | Path) -> ProjectConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError([f"no existe el archivo {path}"])
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ConfigError([f"sintaxis inválida en {path}: {exc}"]) from None
    return parse_config(data)


def config_fingerprint(effective: dict[str, Any]) -> str:
    """SHA-256 de la configuración efectiva (variables ya expandidas; nunca contiene secretos)."""
    canonical = json.dumps(effective, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def config_summary(cfg: ProjectConfig) -> dict[str, Any]:
    """Resumen apto para informes: excluye cualquier valor que pudiera ser sensible."""
    return {
        "project": cfg.project.name,
        "target_url": cfg.target_url,
        "method": cfg.extraction.method,
        "authorization": {
            "confirmed": cfg.authorization.confirmed,
            "authorized_by": cfg.authorization.authorized_by,
            "purpose": cfg.authorization.purpose,
            "terms_reviewed": cfg.authorization.terms_reviewed,
            "environment": cfg.authorization.environment,
            "evidence_reference": cfg.authorization.evidence_reference,
            "allow_authentication": cfg.authorization.allow_authentication,
            "valid_until": str(cfg.authorization.valid_until) if cfg.authorization.valid_until else None,
        },
        "scope": cfg.scope.model_dump(),
        "limits": cfg.limits.model_dump(),
        "fields": [f.name for f in cfg.extraction.fields],
        "pagination": cfg.extraction.pagination.mode,
        "auth": {
            "type": cfg.auth.type,
            "username_env": cfg.auth.username_env,
            "password_env": cfg.auth.password_env,
        },
        "outputs": cfg.output.formats,
    }
