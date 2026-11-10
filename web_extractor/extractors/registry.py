"""Registro de adaptadores: el motor elige por nombre de método, nunca por sitio."""

from __future__ import annotations

from web_extractor.extractors.api_json import DocumentedApiAdapter
from web_extractor.extractors.base import AcquisitionContext, BaseAdapter
from web_extractor.extractors.browser_selenium import SeleniumBrowserAdapter
from web_extractor.extractors.static_html import StaticHtmlAdapter
from web_extractor.extractors.structured_file import StructuredFileAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    StaticHtmlAdapter.name: StaticHtmlAdapter,
    SeleniumBrowserAdapter.name: SeleniumBrowserAdapter,
    StructuredFileAdapter.name: StructuredFileAdapter,
    DocumentedApiAdapter.name: DocumentedApiAdapter,
}


def available_methods() -> list[str]:
    return sorted(ADAPTERS)


def create_adapter(method: str, ctx: AcquisitionContext) -> BaseAdapter:
    try:
        return ADAPTERS[method](ctx)
    except KeyError:
        raise ValueError(f"Método sin adaptador: {method}. Disponibles: {available_methods()}") from None
