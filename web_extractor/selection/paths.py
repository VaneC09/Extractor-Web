"""Rutas con puntos para JSON: ``data.items``, ``price.amount``, ``tags.0``."""

from __future__ import annotations

from typing import Any

_MISSING = object()


def get_path(data: Any, path: str | None, default: Any = None) -> Any:
    if path is None or path in ("", "."):
        return data
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part, _MISSING)
        elif isinstance(current, list) and part.lstrip("-").isdigit():
            index = int(part)
            current = current[index] if -len(current) <= index < len(current) else _MISSING
        else:
            current = _MISSING
        if current is _MISSING:
            return default
    return current


def key_paths(data: Any, prefix: str = "", depth: int = 2) -> list[str]:
    """Firma estructural de un objeto JSON (claves hasta ``depth`` niveles)."""
    if depth < 0 or not isinstance(data, dict):
        return []
    paths: list[str] = []
    for key, value in data.items():
        full = f"{prefix}{key}"
        paths.append(full)
        paths.extend(key_paths(value, full + ".", depth - 1))
    return sorted(paths)
