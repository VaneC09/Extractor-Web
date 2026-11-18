"""Archivo estructurado descargable y autorizado (CSV o JSON) en una única solicitud."""

from __future__ import annotations

from typing import Iterator

from web_extractor.core.auth import form_login
from web_extractor.core.errors import ExtractionError
from web_extractor.extractors.base import BaseAdapter
from web_extractor.models.results import FetchedDocument


class StructuredFileAdapter(BaseAdapter):
    name = "structured_file"

    def iter_documents(self) -> Iterator[FetchedDocument]:
        ctx = self.ctx
        fmt = ctx.cfg.extraction.file_format
        if ctx.cfg.auth.type == "form":
            form_login(ctx.client, ctx.cfg.auth)
        ctx.budget.consume_page()
        accept = "text/csv" if fmt == "csv" else "application/json"
        doc = ctx.client.get(ctx.cfg.target_url, purpose=f"descarga de archivo {fmt}", accept=accept)
        if doc.truncated:
            raise ExtractionError("El archivo supera limits.max_response_bytes; no se procesa parcialmente")
        if "html" in doc.content_type:
            raise ExtractionError(f"Se esperaba {fmt} pero se recibió {doc.content_type}; revise la URL del archivo")
        yield doc
