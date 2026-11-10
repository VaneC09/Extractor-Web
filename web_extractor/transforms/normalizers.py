"""Normalizadores configurables por nombre (``fields[].normalize`` en YAML).

Cada normalizador recibe y devuelve texto (o ``None``); los valores no textuales (números de
un JSON, por ejemplo) se dejan intactos. Para añadir uno nuevo basta registrarlo en
``NORMALIZERS``: la validación de configuración lo reconocerá automáticamente.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable

Normalizer = Callable[[str], "str | None"]

_CURRENCY = re.compile(r"(?i)(?:US\$|MX\$|\$|€|£|¥|\b(?:MXN|USD|EUR|GBP|COP|ARS|CLP|PEN)\b)")
_EMPTY_TOKENS = {"", "-", "—", "n/a", "na", "n/d", "nd", "null", "none", "sin dato", "s/d"}


def _decimal_comma(value: str) -> str:
    """``1.234,50`` -> ``1234.50`` (formato europeo/latino)."""
    return value.replace(".", "").replace(",", ".")


def _strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


NORMALIZERS: dict[str, Normalizer] = {
    "strip": str.strip,
    "collapse_whitespace": lambda v: " ".join(v.split()),
    "lower": str.lower,
    "upper": str.upper,
    "title": str.title,
    "strip_accents": _strip_accents,
    "remove_currency": lambda v: _CURRENCY.sub("", v).strip(),
    "remove_percent": lambda v: v.replace("%", "").strip(),
    "thousands_comma": lambda v: v.replace(",", ""),
    "decimal_comma": _decimal_comma,
    "digits_only": lambda v: re.sub(r"\D", "", v),
    "empty_to_none": lambda v: None if v.strip().lower() in _EMPTY_TOKENS else v,
}


def apply_normalizer(name: str, value: object) -> object:
    if value is None or not isinstance(value, str):
        return value
    return NORMALIZERS[name](value)
