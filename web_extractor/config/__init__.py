"""Configuración del proyecto: esquema validado (Pydantic) y cargador YAML/JSON."""

from web_extractor.config.loader import config_summary, load_config, parse_config
from web_extractor.config.schema import ProjectConfig

__all__ = ["ProjectConfig", "config_summary", "load_config", "parse_config"]
