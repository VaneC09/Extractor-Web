"""Validadores declarativos (``fields[].validate``). Devuelven una lista de errores legibles."""

from __future__ import annotations

import re
from typing import Protocol


class RuleLike(Protocol):
    regex: str | None
    min: float | None
    max: float | None
    choices: list[str] | None
    min_length: int | None
    max_length: int | None


def validate_value(value: object, rule: RuleLike | None) -> list[str]:
    if rule is None or value is None:
        return []
    errors: list[str] = []
    if rule.regex is not None and not re.fullmatch(rule.regex, str(value)):
        errors.append(f"no cumple el patrón {rule.regex!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if rule.min is not None and value < rule.min:
            errors.append(f"{value} < mínimo {rule.min}")
        if rule.max is not None and value > rule.max:
            errors.append(f"{value} > máximo {rule.max}")
    if rule.choices is not None and str(value) not in rule.choices:
        errors.append(f"'{value}' no está en {rule.choices}")
    if isinstance(value, str):
        if rule.min_length is not None and len(value) < rule.min_length:
            errors.append(f"longitud {len(value)} < {rule.min_length}")
        if rule.max_length is not None and len(value) > rule.max_length:
            errors.append(f"longitud {len(value)} > {rule.max_length}")
    return errors
