"""Protocolo común de inspectores.

Un inspector recibe un documento ya obtenido (no realiza solicitudes propias) y devuelve
hallazgos con evidencia. Así el número de solicitudes del diagnóstico lo controla solo el motor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from web_extractor.models.results import FetchedDocument, Finding


@dataclass
class InspectionOutput:
    findings: list[Finding] = field(default_factory=list)
    candidates: dict[str, Any] = field(default_factory=dict)


class Inspector(Protocol):
    name: str

    def applies_to(self, doc: FetchedDocument) -> bool: ...

    def inspect(self, doc: FetchedDocument) -> InspectionOutput: ...


def default_inspectors() -> list[Inspector]:
    from web_extractor.inspectors.html_inspector import HtmlInspector
    from web_extractor.inspectors.response_inspector import ResponseInspector
    from web_extractor.inspectors.structured_inspector import StructuredInspector

    return [ResponseInspector(), HtmlInspector(), StructuredInspector()]


def run_inspectors(doc: FetchedDocument, inspectors: list[Inspector] | None = None) -> InspectionOutput:
    combined = InspectionOutput()
    for inspector in inspectors or default_inspectors():
        if inspector.applies_to(doc):
            output = inspector.inspect(doc)
            combined.findings.extend(output.findings)
            combined.candidates.update(output.candidates)
    return combined
