"""HTML estático con Requests + BeautifulSoup, con paginación por enlace o por plantilla."""

from __future__ import annotations

from typing import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from web_extractor.core.auth import form_login
from web_extractor.core.errors import HTTPStatusError
from web_extractor.extractors.base import BaseAdapter
from web_extractor.models.results import FetchedDocument


def find_next_link(html: str, base_url: str, selector: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    element = soup.select_one(selector)
    if element is None:
        return None
    if element.name != "a":
        element = element.find("a", href=True) or element
    href = element.get("href")
    if not href or href.startswith(("#", "javascript:")) or element.get("aria-disabled") == "true":
        return None
    return urljoin(base_url, href)


class StaticHtmlAdapter(BaseAdapter):
    name = "static_html"

    def iter_documents(self) -> Iterator[FetchedDocument]:
        ctx = self.ctx
        cfg = ctx.cfg
        pagination = cfg.extraction.pagination
        if cfg.auth.type == "form":
            form_login(ctx.client, cfg.auth)

        page_number = pagination.start_page
        url: str | None = (
            pagination.url_template.format(page=page_number) if pagination.mode == "url_template" else cfg.target_url
        )
        visited: set[str] = set()
        index = 0
        while url:
            ctx.budget.consume_page()
            try:
                doc = ctx.client.get(url, purpose=f"página {index + 1}")
            except HTTPStatusError as exc:
                if pagination.mode == "url_template" and index > 0 and exc.status == 404:
                    ctx.actions.record("pagination_end", url, "404 en plantilla: fin de páginas")
                    return
                raise
            doc.page_index = index
            visited.add(url)
            yield doc

            if pagination.mode == "next_link":
                next_url = find_next_link(doc.text, doc.final_url, pagination.next_selector or "")
            elif pagination.mode == "url_template":
                if ctx.last_page_records == 0:
                    ctx.actions.record("pagination_end", url, "página sin registros")
                    return
                page_number += 1
                next_url = pagination.url_template.format(page=page_number)  # type: ignore[union-attr]
            else:
                next_url = None
            if next_url and next_url in visited:
                ctx.actions.record("pagination_loop", next_url, "enlace ya visitado; se detiene", "stop")
                return
            url = next_url
            index += 1
        ctx.actions.record("pagination_end", cfg.target_url, f"{index} página(s) recorridas")
