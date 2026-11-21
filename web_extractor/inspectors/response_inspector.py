"""Indicios a nivel de respuesta HTTP: tipo de contenido, tamaño, cabeceras informativas."""

from __future__ import annotations

from web_extractor.inspectors.base import InspectionOutput
from web_extractor.models.results import FetchedDocument, Finding


class ResponseInspector:
    name = "response"

    def applies_to(self, doc: FetchedDocument) -> bool:
        return True

    def inspect(self, doc: FetchedDocument) -> InspectionOutput:
        out = InspectionOutput()
        ct = doc.content_type or "(sin content-type)"
        out.findings.append(Finding("response.status", "respuesta", f"HTTP {doc.status}, {ct}, "
                                    f"{len(doc.text):,} caracteres", f"vía {doc.via}"))
        if doc.final_url != doc.url:
            out.findings.append(Finding("response.redirect", "respuesta", "Hubo redirección dentro del alcance",
                                        f"{doc.url} -> {doc.final_url}"))
        if doc.truncated:
            out.findings.append(Finding("response.truncated", "limitación",
                                        "Respuesta truncada por limits.max_response_bytes"))
        if doc.is_json:
            out.findings.append(Finding("response.json", "estructurado", "La URL entrega JSON directamente",
                                        ct, {"structured_file": 0.55, "api": 0.25, "static_html": -0.35, "browser": -0.15}))
        elif doc.is_xml:
            out.findings.append(Finding("response.xml", "estructurado", "La URL entrega XML directamente",
                                        ct, {"structured_file": 0.7, "static_html": -0.35, "browser": -0.15}))
        elif doc.is_csv:
            out.findings.append(Finding("response.csv", "estructurado", "La URL entrega CSV directamente",
                                        ct, {"structured_file": 0.8, "static_html": -0.35, "browser": -0.15}))
        if link := doc.headers.get("link") or doc.headers.get("Link"):
            if 'rel="next"' in link:
                out.findings.append(Finding("response.link_next", "paginación",
                                            "Cabecera Link con rel=next", link[:200]))
        for key in ("x-ratelimit-limit", "x-ratelimit-remaining", "retry-after"):
            for header, value in doc.headers.items():
                if header.lower() == key:
                    out.findings.append(Finding(f"response.{key}", "límites",
                                                f"El sitio publica límites de tasa ({header})", value))
        for header, value in doc.headers.items():
            if header.lower() == "x-robots-tag":
                out.findings.append(Finding("response.x_robots", "política", "Cabecera X-Robots-Tag", value))
        return out
