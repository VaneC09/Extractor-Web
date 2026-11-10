"""Esquema de configuración. Todo lo que cambia entre sitios vive aquí, no en el código.

Principios:
- ``extra="forbid"``: una clave desconocida (p. ej. ``password:``) invalida el archivo, lo que
  impide guardar secretos por error y detecta erratas.
- Límites con topes máximos conservadores; para destinos remotos se exige pausa >= 1 s.
- Las credenciales solo se referencian por **nombre de variable de entorno**.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from web_extractor.core.errors import ScopeError
from web_extractor.core.scope import SUPPORTED_SCHEMES, is_private_host, validate_url
from web_extractor.transforms.casting import SUPPORTED_TYPES
from web_extractor.transforms.normalizers import NORMALIZERS

Method = Literal["auto", "static_html", "browser", "structured_file", "api"]
EXECUTABLE_METHODS = ("static_html", "browser", "structured_file", "api")

SENSITIVE_FIELD_NAME = re.compile(
    r"(password|passwd|contrase|secret|token|api_?key|curp|\brfc\b|ssn|\bnss\b|tarjeta|card_?number|"
    r"cvv|clabe|iban|pasaporte|passport)",
    re.I,
)

MIN_REMOTE_DELAY = 1.0


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectInfo(StrictModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$", description="Identificador (slug)")
    description: str = ""


class AuthorizationConfig(StrictModel):
    """Confirmación humana de autorización. La herramienta no puede verificarla por sí misma."""

    confirmed: bool = False
    authorized_by: str | None = None
    purpose: str | None = None
    terms_reviewed: bool = False
    evidence_reference: str | None = None
    environment: Literal["fixture", "test", "production"] = "fixture"
    allow_authentication: bool = False
    personal_data: Literal["none", "minimal_non_sensitive"] = "none"
    valid_until: date | None = None


class ScopeConfig(StrictModel):
    allowed_domains: list[str] = Field(min_length=1)
    allowed_path_prefixes: list[str] = Field(default_factory=lambda: ["/"])
    allowed_schemes: list[Literal["http", "https"]] = Field(default_factory=lambda: ["https"])
    allow_private_network: bool = False
    respect_robots_txt: bool = True

    @field_validator("allowed_path_prefixes")
    @classmethod
    def _prefixes(cls, value: list[str]) -> list[str]:
        if not value or any(not p.startswith("/") for p in value):
            raise ValueError("cada prefijo de ruta debe empezar por '/'")
        return value


class LimitsConfig(StrictModel):
    max_pages: int = Field(3, ge=1, le=100)
    max_records: int = Field(100, ge=1, le=10_000)
    max_requests: int = Field(10, ge=1, le=500)
    max_seconds: float = Field(120, gt=0, le=3600)
    delay_seconds: float = Field(2.0, ge=0, le=60)
    timeout_seconds: float = Field(15, gt=0, le=120)
    max_retries: int = Field(1, ge=0, le=3)
    max_clicks: int = Field(3, ge=0, le=50)
    max_scrolls: int = Field(3, ge=0, le=50)
    max_response_bytes: int = Field(5_000_000, ge=10_000, le=50_000_000)
    concurrency: Literal[1] = 1


class DiagnosisConfig(StrictModel):
    max_requests: int = Field(3, ge=1, le=5, description="Incluye robots.txt y una redirección")
    render_with_browser: bool = False


class ValidationRule(StrictModel):
    regex: str | None = None
    min: float | None = None
    max: float | None = None
    choices: list[str] | None = None
    min_length: int | None = Field(None, ge=0)
    max_length: int | None = Field(None, ge=1)

    @field_validator("regex")
    @classmethod
    def _regex(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(f"expresión regular inválida: {exc}") from exc
        return value


class FieldRule(StrictModel):
    name: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
    selector: str | None = Field(None, description="CSS relativo al registro (HTML)")
    path: str | None = Field(None, description="Ruta con puntos en JSON o columna CSV")
    column: str | None = Field(None, description="Encabezado de columna en tablas HTML")
    attribute: str = Field("text", description="'text', 'html' o nombre de atributo (href, src...)")
    type: str = "string"
    required: bool = False
    normalize: list[str] = Field(default_factory=list)
    pattern: str | None = Field(None, description="Regex; se conserva el grupo 1 (o la coincidencia)")
    date_format: str | None = None
    rules: ValidationRule | None = Field(None, alias="validate")

    @field_validator("name")
    @classmethod
    def _not_sensitive(cls, value: str) -> str:
        if SENSITIVE_FIELD_NAME.search(value):
            raise ValueError(
                f"el campo '{value}' parece un dato sensible o un secreto; no se permite recopilarlo"
            )
        return value

    @field_validator("type")
    @classmethod
    def _type(cls, value: str) -> str:
        if value not in SUPPORTED_TYPES:
            raise ValueError(f"tipo '{value}' no soportado; use uno de {SUPPORTED_TYPES}")
        return value

    @field_validator("normalize")
    @classmethod
    def _normalizers(cls, value: list[str]) -> list[str]:
        unknown = [n for n in value if n not in NORMALIZERS]
        if unknown:
            raise ValueError(f"normalizadores desconocidos {unknown}; disponibles: {sorted(NORMALIZERS)}")
        return value

    @field_validator("pattern")
    @classmethod
    def _pattern(cls, value: str | None) -> str | None:
        if value is not None:
            re.compile(value)
        return value


class PaginationConfig(StrictModel):
    mode: Literal["none", "next_link", "url_template", "page_param", "next_field"] = "none"
    next_selector: str | None = None
    url_template: str | None = None
    page_param: str = "page"
    start_page: int = Field(1, ge=0)
    next_field: str | None = None

    @model_validator(mode="after")
    def _requirements(self) -> "PaginationConfig":
        if self.mode == "next_link" and not self.next_selector:
            raise ValueError("pagination.mode=next_link requiere next_selector")
        if self.mode == "url_template" and (not self.url_template or "{page}" not in self.url_template):
            raise ValueError("pagination.mode=url_template requiere url_template con '{page}'")
        if self.mode == "next_field" and not self.next_field:
            raise ValueError("pagination.mode=next_field requiere next_field")
        return self


class BrowserConfig(StrictModel):
    headless: bool = True
    wait_selector: str | None = None
    wait_timeout_seconds: float = Field(10, gt=0, le=60)
    page_load_timeout_seconds: float = Field(20, gt=0, le=120)
    load_more_selector: str | None = None
    infinite_scroll: bool = False
    scroll_pause_seconds: float = Field(1.0, ge=0.1, le=10)


class ApiConfig(StrictModel):
    """Solo APIs documentadas públicamente y autorizadas. Nunca se infieren endpoints."""

    documented: bool = False
    documentation_url: str | None = None
    accept: str = "application/json"


class ExtractionConfig(StrictModel):
    method: Method = "auto"
    record_selector: str | None = None
    table_selector: str | None = None
    records_path: str | None = None
    file_format: Literal["json", "csv"] | None = None
    fields: list[FieldRule] = Field(min_length=1)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    deduplicate_on: list[str] = Field(default_factory=list)
    keep_raw: bool = True
    drop_invalid: bool = False

    @model_validator(mode="after")
    def _consistency(self) -> "ExtractionConfig":
        names = [f.name for f in self.fields]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"nombres de campo repetidos: {sorted(dupes)}")
        missing = [d for d in self.deduplicate_on if d not in names]
        if missing:
            raise ValueError(f"deduplicate_on usa campos inexistentes: {missing}")

        html_methods = ("static_html", "browser")
        if self.method in html_methods and not (self.record_selector or self.table_selector):
            raise ValueError(f"method={self.method} requiere record_selector o table_selector")
        if self.method == "structured_file" and not self.file_format:
            raise ValueError("method=structured_file requiere file_format (json o csv)")
        if self.method in ("api", "structured_file"):
            no_path = [f.name for f in self.fields if not f.path]
            if no_path:
                raise ValueError(f"method={self.method}: los campos {no_path} requieren 'path'")
        if self.table_selector:
            no_col = [f.name for f in self.fields if not f.column]
            if no_col:
                raise ValueError(f"table_selector: los campos {no_col} requieren 'column'")
        mode = self.pagination.mode
        if mode in ("page_param", "next_field") and self.method not in ("api", "auto"):
            raise ValueError(f"pagination.mode={mode} solo aplica a method=api")
        if mode in ("next_link", "url_template") and self.method in ("api", "structured_file"):
            raise ValueError(f"pagination.mode={mode} solo aplica a HTML (static_html/browser)")
        if self.method != "browser" and (self.browser.load_more_selector or self.browser.infinite_scroll):
            raise ValueError("load_more_selector/infinite_scroll requieren method=browser")
        return self


class AuthConfig(StrictModel):
    """Autenticación por formulario, solo con autorización expresa y credenciales del usuario."""

    type: Literal["none", "form"] = "none"
    login_url: str | None = None
    username_field: str = "username"
    password_field: str = "password"
    username_env: str | None = Field(None, pattern=r"^[A-Z_][A-Z0-9_]*$")
    password_env: str | None = Field(None, pattern=r"^[A-Z_][A-Z0-9_]*$")
    failure_text: str | None = None

    @model_validator(mode="after")
    def _requirements(self) -> "AuthConfig":
        if self.type == "form" and not (self.login_url and self.username_env and self.password_env):
            raise ValueError("auth.type=form requiere login_url, username_env y password_env")
        return self


class OutputConfig(StrictModel):
    directory: str = "outputs"
    formats: list[Literal["csv", "json", "sqlite"]] = Field(default_factory=lambda: ["csv", "json", "sqlite"])
    sqlite_path: str | None = None
    stop_file: str = "STOP"
    profile_name: str | None = Field(None, pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")


class ProjectConfig(StrictModel):
    version: Literal[1] = 1
    project: ProjectInfo
    target_url: str
    user_agent: str = Field(
        "WebExtractorAcademico/0.1 (+proyecto academico; contacto: configurar)",
        min_length=10,
        max_length=200,
    )
    authorization: AuthorizationConfig = Field(default_factory=AuthorizationConfig)
    scope: ScopeConfig
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    diagnosis: DiagnosisConfig = Field(default_factory=DiagnosisConfig)
    extraction: ExtractionConfig
    auth: AuthConfig = Field(default_factory=AuthConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @field_validator("target_url")
    @classmethod
    def _target_scheme(cls, value: str) -> str:
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("solo se admiten URLs http(s); otros protocolos (ftp, file, data...) se rechazan")
        return value.strip()

    @model_validator(mode="after")
    def _cross_checks(self) -> "ProjectConfig":
        scope = self.scope
        try:
            validate_url(
                self.target_url,
                allowed_schemes=scope.allowed_schemes,
                allowed_domains=scope.allowed_domains,
                allowed_path_prefixes=scope.allowed_path_prefixes,
                allow_private_network=scope.allow_private_network,
            )
            if self.auth.login_url:
                validate_url(
                    self.auth.login_url,
                    allowed_schemes=scope.allowed_schemes,
                    allowed_domains=scope.allowed_domains,
                    allowed_path_prefixes=scope.allowed_path_prefixes,
                    allow_private_network=scope.allow_private_network,
                )
        except ScopeError as exc:
            raise ValueError(f"target_url/login_url fuera del alcance: {exc}") from exc

        if any(s not in SUPPORTED_SCHEMES for s in scope.allowed_schemes):
            raise ValueError("solo se admiten http/https")
        remote = not all(is_private_host(d.lstrip("*.")) for d in scope.allowed_domains)
        if remote and self.limits.delay_seconds < MIN_REMOTE_DELAY:
            raise ValueError(f"para destinos remotos limits.delay_seconds debe ser >= {MIN_REMOTE_DELAY}")
        if remote and scope.allow_private_network:
            raise ValueError("allow_private_network solo puede usarse con dominios locales (fixtures)")
        if self.auth.type != "none" and not self.authorization.allow_authentication:
            raise ValueError("auth configurada sin authorization.allow_authentication=true")
        if self.auth.type != "none" and self.extraction.method == "browser":
            raise ValueError("autenticación con navegador no está soportada en el MVP (use static_html)")
        if self.extraction.api.documentation_url:
            if not self.extraction.api.documentation_url.startswith(("https://", "http://")):
                raise ValueError("api.documentation_url debe ser http(s)")
        return self

    @property
    def profile_name(self) -> str:
        return self.output.profile_name or self.project.name
