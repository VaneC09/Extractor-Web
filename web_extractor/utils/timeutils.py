"""Marcas de tiempo en UTC (ISO 8601) e identificadores de ejecución."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")


def new_run_id() -> str:
    return f"{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"
