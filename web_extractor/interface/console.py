"""Presentación en consola de diagnóstico, vista previa y resultados; confirmaciones explícitas."""

from __future__ import annotations

import sys
import textwrap

import pandas as pd

from web_extractor.config.schema import ProjectConfig
from web_extractor.models.results import Diagnosis, PreviewResult, RunResult
from web_extractor.reports.intervention import guide_for
from web_extractor.reports.run_report import STATUS_TEXT


def out(text: str = "") -> None:
    print(text, file=sys.stdout, flush=True)


def heading(title: str) -> None:
    out()
    out(f"== {title} " + "=" * max(0, 70 - len(title)))


def ask_yes_no(question: str) -> bool:
    """Exige escribir 'si' (o 'sí'/'s'/'yes'); cualquier otra respuesta es 'no'."""
    if not sys.stdin.isatty():
        out(f"{question} [no interactivo: se asume NO]")
        return False
    try:
        answer = input(f"{question} Escriba 'si' para confirmar: ").strip().lower()
    except EOFError:
        out(" [sin respuesta: se asume NO]")
        return False
    return answer in ("si", "sí", "s", "yes", "y")


def ask(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{question}{suffix}: ").strip()
    return answer or default


def show_authorization(cfg: ProjectConfig, missing: list[str]) -> None:
    a = cfg.authorization
    heading("Autorización, alcance y límites")
    out(f"URL objetivo:    {cfg.target_url}")
    out(f"Entorno:         {a.environment}")
    out(f"Autoriza:        {a.authorized_by or '(sin indicar)'}")
    out(f"Finalidad:       {a.purpose or '(sin indicar)'}")
    out(f"Términos:        {'revisados' if a.terms_reviewed else 'NO revisados'}")
    out(f"Confirmado:      {'sí' if a.confirmed else 'no'}")
    out(f"Dominios:        {', '.join(cfg.scope.allowed_domains)}  rutas: {', '.join(cfg.scope.allowed_path_prefixes)}")
    lim = cfg.limits
    out(f"Límites:         {lim.max_requests} solicitudes, {lim.max_pages} páginas, {lim.max_records} registros, "
        f"{lim.max_seconds:.0f} s, pausa {lim.delay_seconds} s, concurrencia 1")
    if missing:
        out("\nFalta para extraer (solo se permite diagnóstico pasivo / fixtures):")
        for item in missing:
            out(f"  - {item}")


def show_diagnosis(d: Diagnosis) -> None:
    heading("Diagnóstico")
    out(f"Estado: {d.status_code}  Tipo: {d.content_type or '—'}  Solicitudes usadas: {d.requests_used}")
    for incident in d.incidents:
        out(f"\n[PARADA] {incident.kind}: {incident.message}")
        out(f"         Siguiente paso legítimo: {incident.next_step}")
        show_guide(incident.kind)
    if d.findings:
        out("\nIndicios observados (heurísticos):")
        for f in d.findings:
            out(f"  - [{f.category}] {f.message}")
            if f.evidence:
                out(textwrap.indent(textwrap.shorten(f.evidence, 150), "      evidencia: "))
    if d.recommendations:
        out("\nMétodos (puntuación / confianza):")
        for r in d.recommendations:
            flag = "" if r.executable else "  -> NO VERIFICADO / NO EJECUTAR"
            out(f"  {r.method:16} {r.score:.2f}  {r.confidence:5}{flag}")
            for req in r.requirements:
                out(f"      · {req}")
    out("\nLimitaciones:")
    for item in d.limitations:
        out(f"  - {item}")


def show_guide(kind: str) -> None:
    guide = guide_for(kind)
    if guide is None:
        return
    out(f"         ¿Se puede continuar? {guide['answer']}")
    for n, step in enumerate(guide["steps"], 1):
        out(textwrap.fill(step, 100, initial_indent=f"         {n}. ", subsequent_indent="            "))


def show_files(files: dict[str, str]) -> None:
    labels = {"intervention": "Pasos de intervención humana", "markdown": "Informe de diagnóstico",
              "actions": "Bitácora de acciones", "log": "Log", "folder": "Carpeta"}
    shown = [(labels[k], files[k]) for k in labels if files.get(k)]
    if shown:
        out("\nRegistros guardados:")
        for label, path in shown:
            out(f"  {label}: {path}")


def records_frame(preview_records) -> pd.DataFrame:
    rows = []
    for r in preview_records:
        row = dict(r.data)
        row["_estado"] = r.lineage["validation_status"]
        rows.append(row)
    return pd.DataFrame(rows, dtype=object).fillna("—")


def show_preview(p: PreviewResult) -> None:
    heading(f"Vista previa ({len(p.records)} registros) — origen: {p.source}")
    for incident in p.incidents:
        out(f"[PARADA] {incident.kind}: {incident.message}\n         Siguiente paso: {incident.next_step}")
    if not p.records:
        out("Sin registros: revise record_selector/table_selector/records_path y los selectores de campos.")
        return
    with pd.option_context("display.max_columns", 20, "display.width", 160, "display.max_colwidth", 40):
        out(records_frame(p.records).to_string(index=False))
    q = p.quality
    out(f"\nVálidos {q.valid} · advertencias {q.with_warnings} · inválidos {q.invalid} · duplicados {q.duplicates_removed}")
    for sample in q.error_samples[:8]:
        out(f"  - {sample}")
    out(f"Solicitudes usadas por la vista previa: {p.requests_used}")


def show_run(r: RunResult) -> None:
    heading(f"Resultado de la ejecución {r.run_id}")
    out(f"Estado: {r.status} — {STATUS_TEXT.get(r.status, '')}")
    out(f"Detalle: {r.status_message}")
    b = r.budget
    out(f"Consumo: {b.get('requests')}/{b.get('max_requests')} solicitudes, {b.get('pages')}/{b.get('max_pages')} páginas, "
        f"{b.get('records')}/{b.get('max_records')} registros, {b.get('elapsed_seconds')} s")
    q = r.quality
    out(f"Calidad: {q.exported} exportados · válidos {q.valid} · advertencias {q.with_warnings} · "
        f"inválidos {q.invalid} · duplicados eliminados {q.duplicates_removed}")
    for incident in r.incidents:
        out(f"Incidencia [{incident.severity}] {incident.kind}: {incident.message}")
        show_guide(incident.kind)
    for change in r.profile_changes:
        out(f"Cambio [{change['severity']}] {change['kind']}: {change['message']}")
    if r.requires_human_review:
        out("REVISIÓN HUMANA REQUERIDA: no se actualizó el perfil ni se corrigió nada automáticamente.")
    out("Archivos:")
    for name, path in r.outputs.items():
        out(f"  {name:8} {path}")
    out("Siguientes pasos:")
    for step in r.next_steps:
        out(f"  - {step}")
