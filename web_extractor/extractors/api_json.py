"""API pública y documentada (JSON). Solo consume la URL configurada y la paginación que la
propia respuesta o la documentación declaran; nunca descubre ni prueba endpoints."""

from __future__ import annotations

import json
from typing import Iterator
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from web_extractor.core.auth import form_login
from web_extractor.core.errors import AuthorizationError
from web_extractor.extractors.base import BaseAdapter
from web_extractor.models.results import FetchedDocument
from web_extractor.selection.paths import get_path


def with_query_param(url: str, name: str, value: object) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != name]
    query.append((name, str(value)))
    return urlunsplit(parts._replace(query=urlencode(query)))


class DocumentedApiAdapter(BaseAdapter):
    name = "api"

    def iter_documents(self) -> Iterator[FetchedDocument]:
        ctx = self.ctx
        cfg = ctx.cfg
        api = cfg.extraction.api
        if not (api.documented and api.documentation_url):
            raise AuthorizationError(["API no verificada como pública y documentada: no ejecutar"])
        if cfg.auth.type == "form":
            form_login(ctx.client, cfg.auth)
        pagination = cfg.extraction.pagination
        page = pagination.start_page
        url: str | None = (
            with_query_param(cfg.target_url, pagination.page_param, page)
            if pagination.mode == "page_param" else cfg.target_url
        )
        visited: set[str] = set()
        index = 0
        while url:
            ctx.budget.consume_page()
            doc = ctx.client.get(url, purpose=f"API página {index + 1}", accept=api.accept)
            doc.page_index = index
            visited.add(url)
            yield doc
            next_url: str | None = None
            if pagination.mode == "next_field":
                try:
                    nxt = get_path(json.loads(doc.text), pagination.next_field)
                except json.JSONDecodeError:
                    nxt = None
                next_url = urljoin(doc.final_url, nxt) if isinstance(nxt, str) and nxt else None
            elif pagination.mode == "page_param" and ctx.last_page_records:
                page += 1
                next_url = with_query_param(cfg.target_url, pagination.page_param, page)
            if next_url in visited:
                ctx.actions.record("pagination_loop", next_url or "", "URL repetida; se detiene", "stop")
                return
            url = next_url
            index += 1
