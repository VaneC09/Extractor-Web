"""Informe de diagnóstico/viabilidad en Markdown y JSON."""

from __future__ import annotations

import json
from pathlib import Path

from web_extractor.models.results import Diagnosis


def diagnosis_markdown(d: Diagnosis) -> str:
    lines = [f"# Diagnóstico de `{d.target_url}`", "",
             f"- Fecha (UTC): {d.fetched_at}",
             f"- URL final: {d.final_url or '—'}",
             f"- Estado HTTP: {d.status_code if d.status_code is not None else '—'}",
             f"- Tipo de contenido: {d.content_type or '—'}",
             f"- Solicitudes usadas: {d.requests_used}",
             f"- Diagnóstico detenido: {'sí' if d.stopped else 'no'}", ""]
    if d.incidents:
        lines += ["## Incidencias", ""]
        for i in d.incidents:
            lines.append(f"- **{i.kind}** — {i.message} ({i.url}). Siguiente paso legítimo: {i.next_step}")
        lines.append("")
    lines += ["## Métodos sugeridos", "", "| Método | Puntuación | Confianza | Ejecutable | Requisitos |",
              "|---|---|---|---|---|"]
    for r in d.recommendations:
        lines.append(f"| {r.method} | {r.score:.2f} | {r.confidence} | {'sí' if r.executable else 'no verificado / no ejecutar'} "
                     f"| {'; '.join(r.requirements) or '—'} |")
    lines.append("")
    for r in d.recommendations:
        if r.reasons or r.against:
            lines.append(f"### {r.method}")
            lines += [f"- A favor: {x}" for x in r.reasons] + [f"- En contra: {x}" for x in r.against]
            lines.append("")
    lines += ["## Hallazgos (indicios heurísticos)", "", "| Código | Categoría | Descripción | Evidencia |", "|---|---|---|---|"]
    for f in d.findings:
        evidence = f.evidence.replace("|", "\\|").replace("\n", " ")[:160]
        lines.append(f"| {f.code} | {f.category} | {f.message.replace('|', '/')} | {evidence} |")
    lines += ["", "## Limitaciones del diagnóstico", ""] + [f"- {x}" for x in d.limitations]
    if d.candidates:
        lines += ["", "## Candidatos detectados", "", "```json",
                  json.dumps(d.candidates, ensure_ascii=False, indent=2)[:4000], "```"]
    return "\n".join(lines) + "\n"


def write_diagnosis(d: Diagnosis, directory: Path, stem: str) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    md = directory / f"{stem}.md"
    js = directory / f"{stem}.json"
    md.write_text(diagnosis_markdown(d), encoding="utf-8")
    js.write_text(json.dumps(d.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": str(md), "json": str(js)}
