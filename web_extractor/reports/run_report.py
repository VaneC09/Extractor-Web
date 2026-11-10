"""Informe de ejecución: resumen, consumo de límites, calidad, incidencias, cambios y pasos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web_extractor.models.results import RunResult

STATUS_TEXT = {
    "completado": "Completado dentro de los límites",
    "completado_con_limites": "Completado parcialmente: se alcanzó un límite configurado",
    "parcial_barrera": "Parcial: se detuvo por una barrera tras obtener algunos datos",
    "detenido_barrera": "Detenido por una barrera antes de obtener datos",
    "detenido_politica": "Detenido por política (alcance, robots.txt o autorización)",
    "cancelado": "Cancelado por el usuario",
    "fallido": "Fallido por un error técnico",
}


def next_steps_for(result: RunResult) -> list[str]:
    steps: list[str] = []
    for incident in result.incidents:
        if incident.next_step and incident.next_step not in steps:
            steps.append(incident.next_step)
    if result.status == "completado_con_limites":
        steps.append("Si necesita más datos, amplíe límites solo dentro de lo autorizado y con pausas adecuadas.")
    if result.requires_human_review:
        steps.append("Revise los cambios detectados frente al perfil anterior antes de volver a ejecutar; "
                     "no se actualizó la línea base.")
    if result.quality.invalid:
        steps.append("Revise los registros inválidos (columna _validation_errors) y ajuste reglas o selectores.")
    if result.status == "completado" and not steps:
        steps.append("Validar muestras manualmente y documentar el resultado en la matriz de pruebas.")
    return steps


def run_markdown(result: RunResult, config_summary: dict[str, Any], notes: list[str]) -> str:
    q = result.quality
    b = result.budget
    lines = [
        f"# Informe de ejecución `{result.run_id}`", "",
        f"- Proyecto: **{result.project}**",
        f"- URL objetivo: {result.target_url}",
        f"- Método: `{result.method}`",
        f"- Estado: **{result.status}** — {STATUS_TEXT.get(result.status, '')}",
        f"- Detalle: {result.status_message}",
        f"- Inicio / fin (UTC): {result.started_at} / {result.finished_at}",
        f"- Revisión humana requerida: {'sí' if result.requires_human_review else 'no'}", "",
        "## Autorización y alcance declarados", "",
        "```json", json.dumps({"authorization": config_summary.get("authorization"), "scope": config_summary.get("scope")},
                              ensure_ascii=False, indent=2), "```", "",
        "## Consumo frente a límites", "",
        "| Recurso | Usado | Límite |", "|---|---|---|",
        f"| Solicitudes/acciones | {b.get('requests')} | {b.get('max_requests')} |",
        f"| Páginas | {b.get('pages')} | {b.get('max_pages')} |",
        f"| Registros crudos | {b.get('records')} | {b.get('max_records')} |",
        f"| Clics / scrolls | {b.get('clicks')} / {b.get('scrolls')} | — |",
        f"| Tiempo (s) | {b.get('elapsed_seconds')} | {b.get('max_seconds')} |", "",
        "## Calidad de datos", "",
        f"- Registros crudos: {q.total_raw}; exportados: {q.exported}",
        f"- Válidos: {q.valid}; con advertencias: {q.with_warnings}; inválidos: {q.invalid}",
        f"- Duplicados eliminados: {q.duplicates_removed}; inválidos descartados: {q.dropped_invalid}", "",
        "| Campo | Con valor | Vacíos | Errores | Tasa de llenado |", "|---|---|---|---|---|",
    ]
    for name, fq in q.fields.items():
        lines.append(f"| {name} | {fq.filled} | {fq.empty} | {fq.invalid} | {fq.fill_rate(q.total_raw):.0%} |")
    if q.error_samples:
        lines += ["", "Muestra de errores de validación:", ""] + [f"- {e}" for e in q.error_samples[:15]]
    lines += ["", "## Incidencias", ""]
    lines += [f"- **{i.kind}** ({i.severity}) {i.message} — {i.url} — Siguiente paso: {i.next_step}"
              for i in result.incidents] or ["- Ninguna"]
    if result.errors:
        lines += ["", "## Errores", ""] + [f"- {e}" for e in result.errors]
    if notes:
        lines += ["", "## Notas", ""] + [f"- {n}" for n in notes]
    lines += ["", "## Cambios frente al perfil anterior", ""]
    lines += [f"- [{c['severity']}] {c['kind']}: {c['message']}" for c in result.profile_changes] or ["- Sin cambios o sin perfil previo"]
    lines += ["", "## Archivos generados", ""] + [f"- {k}: `{v}`" for k, v in result.outputs.items()]
    lines += ["", "## Siguientes pasos", ""] + [f"- {s}" for s in result.next_steps]
    return "\n".join(lines) + "\n"


def write_run_report(result: RunResult, run_dir: Path, config_summary: dict[str, Any], notes: list[str]) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    report = run_dir / "report.md"
    summary = run_dir / "summary.json"
    report.write_text(run_markdown(result, config_summary, notes), encoding="utf-8")
    payload = result.summary_dict() | {"config": config_summary, "notes": notes}
    summary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"report": str(report), "summary": str(summary)}
