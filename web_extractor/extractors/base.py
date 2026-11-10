"""Interfaz común de adaptadores.

Un adaptador solo **adquiere documentos** (navega, pagina, hace clic o scroll dentro de los
topes); no interpreta campos. El motor convierte cada documento en registros con
``selection.field_extractor`` y comunica al adaptador cuántos registros produjo la última
página (``ctx.last_page_records``) para que pueda detener la paginación por plantilla.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterator, Protocol

from web_extractor.config.schema import ProjectConfig
from web_extractor.core.http_client import PoliteHttpClient
from web_extractor.core.limits import Budget, CancelToken, RateLimiter
from web_extractor.core.tracing import ActionLog, IncidentLog
from web_extractor.models.results import FetchedDocument


@dataclass
class AcquisitionContext:
    cfg: ProjectConfig
    client: PoliteHttpClient
    budget: Budget
    rate: RateLimiter
    cancel: CancelToken
    actions: ActionLog
    incidents: IncidentLog
    logger: logging.Logger
    last_page_records: int | None = None
    notes: list[str] = field(default_factory=list)


class Adapter(Protocol):
    name: str

    def iter_documents(self) -> Iterator[FetchedDocument]: ...

    def close(self) -> None: ...


class BaseAdapter:
    name = "base"

    def __init__(self, ctx: AcquisitionContext) -> None:
        self.ctx = ctx

    def iter_documents(self) -> Iterator[FetchedDocument]:  # pragma: no cover - interfaz
        raise NotImplementedError

    def close(self) -> None:
        """Liberar recursos. Debe ser idempotente."""
