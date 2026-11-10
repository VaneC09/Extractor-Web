"""Conversión de tipos declarados en la configuración."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from urllib.parse import urlsplit

SUPPORTED_TYPES = ("string", "integer", "float", "boolean", "date", "datetime", "url")

_TRUE = {"true", "1", "yes", "si", "sí", "y", "s", "verdadero", "disponible", "activo"}
_FALSE = {"false", "0", "no", "n", "falso", "agotado", "no disponible", "inactivo"}


class CastError(ValueError):
    pass


def cast_value(value: object, type_name: str, date_format: str | None = None) -> object:
    if value is None:
        return None
    if type_name == "string":
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)
    if type_name == "integer":
        if isinstance(value, bool):
            raise CastError("booleano no es entero")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        text = str(value).strip()
        if not re.fullmatch(r"[-+]?\d+", text):
            raise CastError(f"'{text}' no es un entero")
        return int(text)
    if type_name == "float":
        if isinstance(value, bool):
            raise CastError("booleano no es numérico")
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not re.fullmatch(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?", text):
            raise CastError(f"'{text}' no es un número")
        return float(text)
    if type_name == "boolean":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise CastError(f"'{value}' no es un booleano reconocido")
    if type_name in ("date", "datetime"):
        text = str(value).strip()
        try:
            parsed = datetime.strptime(text, date_format) if date_format else datetime.fromisoformat(
                text.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise CastError(f"'{text}' no es una fecha válida ({date_format or 'ISO 8601'})") from exc
        return parsed.date().isoformat() if type_name == "date" else parsed.isoformat()
    if type_name == "url":
        text = str(value).strip()
        parts = urlsplit(text)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise CastError(f"'{text}' no es una URL http(s) absoluta")
        return text
    raise CastError(f"tipo no soportado: {type_name}")


def is_date(value: object) -> bool:
    return isinstance(value, date)
