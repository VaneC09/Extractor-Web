"""Motor único de diagnóstico y extracción, guiado por configuración.

El mismo motor sirve para cualquier sitio: lo que cambia es la ``ProjectConfig`` (método,
reglas, límites). No contiene selectores ni URLs de sitios concretos.

Flujo de ``run``:
puerta de autorización -> adaptador (adquisición con límites) -> selección de campos ->
calidad (normalizar, tipos, validar, deduplicar, linaje) -> exportación -> perfil/cambios ->
informe. Cualquier barrera detiene la adquisición y genera una incidencia; lo ya obtenido se
procesa y se marca como resultado parcial.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from web_extractor import __version__
from web_extractor.config.loader import config_fingerprint, config_summary
from web_extractor.config.schema import ProjectConfig
from web_extractor.core.authorization import missing_for_diagnosis, missing_for_extraction
from web_extractor.core.errors import (
    AuthFailed,
    AuthorizationError,
    BarrierDetected,
    BrowserUnavailable,
    Cancelled,
    ExtractionError,
    HTTPStatusError,
    LimitReached,
    RobotsDisallowed,
    ScopeError,
    TransientHTTPError,
)
from web_extractor.core.http_client import PoliteHttpClient, detect_encoding
from web_extractor.core.limits import Budget, CancelToken, LimitValues, RateLimiter
from web_extractor.core.tracing import ActionEntry, ActionLog, IncidentLog
from web_extractor.extractors.base import AcquisitionContext
from web_extractor.extractors.registry import create_adapter
from web_extractor.inspectors.base import run_inspectors
from web_extractor.inspectors.classifier import classify
from web_extractor.models.results import (
    Diagnosis,
    FetchedDocument,
    Finding,
    Incident,
    PreviewResult,
    RawRecord,
    RunResult,
)
from web_extractor.reports.diagnosis_report import write_diagnosis
from web_extractor.reports.intervention import GENERAL_LOG, intervention_entries, write_intervention
from web_extractor.reports.profiles import ProfileStore, build_profile, compare_profiles, requires_review
from web_extractor.reports.run_report import next_steps_for, write_run_report
from web_extractor.selection.field_extractor import parse_document
from web_extractor.storage.exporters import ExportBundle, export_all
from web_extractor.transforms.pipeline import TransformPipeline
from web_extractor.utils.logging_utils import add_file_handler, get_logger, remove_handler
from web_extractor.utils.timeutils import new_run_id, utc_now_iso

DIAGNOSIS_LIMITATIONS = [
    "Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por "
    "usuario, región, hora o pruebas A/B.",
    "Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.",
    "No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.",
    "La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.",
    "La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la "
    "confirmación humana registrada en la configuración.",
]

POLICY_ERRORS = (RobotsDisallowed, ScopeError, AuthorizationError)
TECHNICAL_ERRORS = (HTTPStatusError, TransientHTTPError, ExtractionError, BrowserUnavailable)


class ExtractionEngine:
    def __init__(self, cfg: ProjectConfig, *, cancel: CancelToken | None = None,
                 logger: logging.Logger | None = None,
                 on_action: Callable[[ActionEntry], None] | None = None,
                 code_provider: Callable[[str], str | None] | None = None,
                 human_notice: Callable[[str | None], None] | None = None) -> None:
        self.cfg = cfg
        self.code_provider = code_provider
        self.human_notice = human_notice
        self.output_dir = Path(cfg.output.directory)
        self.cancel = cancel or CancelToken(self.output_dir / cfg.output.stop_file)
        self.logger = logger or get_logger("engine")
        self.on_action = on_action
        self._last_actions: ActionLog | None = None

    # ------------------------------------------------------------------ contexto
    def _limit_values(self, **overrides: float | int) -> LimitValues:
        lim = self.cfg.limits
        values = LimitValues(max_pages=lim.max_pages, max_records=lim.max_records, max_requests=lim.max_requests,
                             max_seconds=lim.max_seconds, max_clicks=lim.max_clicks, max_scrolls=lim.max_scrolls)
        for key, value in overrides.items():
            setattr(values, key, value)
        return values

    def _context(self, limits: LimitValues) -> AcquisitionContext:
        budget = Budget(limits, self.cancel)
        rate = RateLimiter(self.cfg.limits.delay_seconds, self.cancel)
        actions = ActionLog(self.logger, self.on_action)
        incidents = IncidentLog(self.logger)
        client = PoliteHttpClient(self.cfg, budget, rate, self.cancel, actions, self.logger)
        client.code_provider = self.code_provider
        client.human_notice = self.human_notice
        return AcquisitionContext(self.cfg, client, budget, rate, self.cancel, actions, incidents, self.logger)

    @staticmethod
    def _incident_from(exc: Exception, ctx: AcquisitionContext, default_url: str) -> Incident:
        if isinstance(exc, BarrierDetected):
            b = exc.barrier
            message = b.message + (f" — evidencia: {b.evidence}" if b.evidence else "")
            return ctx.incidents.add(b.kind, message, b.url or default_url, b.next_step)
        if isinstance(exc, RobotsDisallowed):
            return ctx.incidents.add("robots_disallow", str(exc), default_url,
                                     "Respetar robots.txt; solicitar permiso explícito o una vía alternativa autorizada.")
        if isinstance(exc, ScopeError):
            return ctx.incidents.add("out_of_scope", str(exc), default_url,
                                     "Ampliar el alcance solo si el propietario lo autoriza; si no, omitir el recurso.")
        if isinstance(exc, AuthorizationError):
            return ctx.incidents.add("authorization", str(exc), default_url, "Completar la autorización en la configuración.")
        if isinstance(exc, AuthFailed):
            return ctx.incidents.add("auth_failed", str(exc), default_url,
                                     "Verificar credenciales autorizadas con el propietario; no se reintenta.")
        if isinstance(exc, Cancelled):
            return ctx.incidents.add("cancelled", str(exc), default_url, "Reanudar solo tras revisión humana.", "media")
        if isinstance(exc, LimitReached):
            return ctx.incidents.add("limit", str(exc), default_url, "Ampliar límites solo dentro de lo autorizado.", "baja")
        return ctx.incidents.add("error", f"{type(exc).__name__}: {exc}", default_url, "Revisar el log de la ejecución.", "media")

    # ---------------------------------------------------------------- diagnóstico
    def diagnose(self, render: bool | None = None) -> Diagnosis:
        missing = missing_for_diagnosis(self.cfg)
        if missing:
            raise AuthorizationError(missing)
        folder = self._event_dir("diagnosticos")
        handlers = self._open_logs(folder / "diagnostico.log")
        try:
            diagnosis = self._diagnose(render)
            diagnosis.files = self._record_event(diagnosis.incidents, "diagnóstico", folder, self._last_actions)
            diagnosis.files.update(write_diagnosis(diagnosis, folder, "diagnostico"))
            diagnosis.files["log"] = str(folder / "diagnostico.log")
            return diagnosis
        finally:
            self._close_logs(handlers)

    # --------------------------------------------------------------- registros
    def _event_dir(self, kind: str) -> Path:
        return self.output_dir / self.cfg.project.name / kind / new_run_id()

    def _open_logs(self, event_log: Path | None = None) -> list:
        handlers = [add_file_handler(self.output_dir / GENERAL_LOG)]
        if event_log is not None:
            handlers.append(add_file_handler(event_log))
        return handlers

    @staticmethod
    def _close_logs(handlers: list) -> None:
        for handler in handlers:
            remove_handler(handler)

    def _record_event(self, incidents: list[Incident], stage: str, folder: Path, actions: ActionLog | None) -> dict[str, str]:
        """Bitácora de acciones y, si hace falta una persona, los pasos a seguir (carpeta + registro central)."""
        files: dict[str, str] = {"folder": str(folder)}
        if actions is not None:
            actions.write_jsonl(folder / "actions.jsonl")
            files["actions"] = str(folder / "actions.jsonl")
        entries = intervention_entries(incidents, stage=stage, project=self.cfg.project.name, target_url=self.cfg.target_url)
        files.update(write_intervention(entries, folder, self.output_dir))
        if entries:
            self.logger.warning("Intervención humana requerida (%s): pasos en %s", stage, files["intervention"])
        return files

    def _diagnose(self, render: bool | None) -> Diagnosis:
        render = self.cfg.diagnosis.render_with_browser if render is None else render
        max_requests = self.cfg.diagnosis.max_requests + (1 if render else 0)
        ctx = self._context(self._limit_values(max_pages=1, max_requests=max_requests,
                                               max_seconds=min(self.cfg.limits.max_seconds, 90), max_clicks=0, max_scrolls=0))
        target = self.cfg.target_url
        diagnosis = Diagnosis(target_url=target, limitations=list(DIAGNOSIS_LIMITATIONS))
        doc: FetchedDocument | None = None
        try:
            doc = ctx.client.get(target, purpose="diagnóstico", auth_expected=self.cfg.auth.type != "none")
        except (BarrierDetected, *POLICY_ERRORS, *TECHNICAL_ERRORS, LimitReached, Cancelled) as exc:
            diagnosis.incidents.append(self._incident_from(exc, ctx, target))
            diagnosis.stopped = True
            if isinstance(exc, BarrierDetected):
                diagnosis.status_code = exc.barrier.status_code
        if doc is not None:
            diagnosis.final_url, diagnosis.status_code = doc.final_url, doc.status
            diagnosis.content_type, diagnosis.fetched_at = doc.content_type, doc.fetched_at
            output = run_inspectors(doc)
            diagnosis.findings, diagnosis.candidates = output.findings, output.candidates
            if render and doc.is_html:
                self._render_compare(ctx, doc, diagnosis)
            diagnosis.recommendations = classify(diagnosis.findings, self.cfg)
        diagnosis.limitations += ctx.client.robots.notes
        diagnosis.requests_used = ctx.budget.requests
        ctx.client.close()
        self._last_actions = ctx.actions
        return diagnosis

    def _render_compare(self, ctx: AcquisitionContext, static_doc: FetchedDocument, diagnosis: Diagnosis) -> None:
        from bs4 import BeautifulSoup

        from web_extractor.extractors.browser_selenium import SeleniumSession

        def visible_len(html: str) -> int:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(["script", "style", "noscript", "template"]):
                tag.extract()
            return len(" ".join(soup.get_text(" ", strip=True).split()))

        session = SeleniumSession(ctx)
        try:
            session.start()
            session.navigate(self.cfg.target_url, "diagnóstico renderizado")
            session.wait_for(self.cfg.extraction.browser.wait_selector, self.cfg.extraction.browser.wait_timeout_seconds)
            ctx.cancel.wait(1.0)
            rendered = session.snapshot(0)
        except (BarrierDetected, *POLICY_ERRORS, BrowserUnavailable, LimitReached, Cancelled) as exc:
            diagnosis.incidents.append(self._incident_from(exc, ctx, self.cfg.target_url))
            if isinstance(exc, (BarrierDetected, *POLICY_ERRORS)):
                diagnosis.stopped = True
            return
        except Exception as exc:  # errores de WebDriver
            diagnosis.limitations.append(f"Render con navegador no disponible: {type(exc).__name__}")
            return
        finally:
            session.close()
        before, after = visible_len(static_doc.text), visible_len(rendered.text)
        if after > max(2 * before, before + 200):
            diagnosis.findings.append(Finding("render.adds_content", "renderizado",
                                              "El render con navegador añade contenido visible significativo",
                                              f"texto estático={before}, renderizado={after}",
                                              {"browser": 0.35, "static_html": -0.25}))
        else:
            diagnosis.findings.append(Finding("render.no_change", "renderizado",
                                              "El render con navegador no añade contenido relevante",
                                              f"texto estático={before}, renderizado={after}",
                                              {"static_html": 0.15, "browser": -0.1}))
        rendered_out = run_inspectors(rendered)
        if "record_selectors" in rendered_out.candidates:
            diagnosis.candidates["rendered_record_selectors"] = rendered_out.candidates["record_selectors"]
        if "tables" in rendered_out.candidates:
            diagnosis.candidates["rendered_tables"] = rendered_out.candidates["tables"]

    # --------------------------------------------------------------- vista previa
    def preview(self, max_records: int = 5, from_file: Path | None = None) -> PreviewResult:
        extraction = self.cfg.extraction
        if from_file is not None:
            raw_bytes = Path(from_file).read_bytes()
            text = raw_bytes.decode(detect_encoding("", raw_bytes), errors="replace")
            suffix = Path(from_file).suffix.lower()
            content_type = {".json": "application/json", ".csv": "text/csv", ".xml": "application/xml"}.get(suffix, "text/html")
            doc = FetchedDocument(self.cfg.target_url, self.cfg.target_url, 200, content_type, text, via="file")
            items = parse_document(doc, extraction).items[:max_records]
            raw = [RawRecord(i, f"file://{Path(from_file).resolve()}", doc.fetched_at, "local_file") for i in items]
            records, quality = TransformPipeline(extraction).process(raw, "preview")
            return PreviewResult(records, quality, f"archivo local {from_file}", 0)

        missing = missing_for_extraction(self.cfg)
        if missing:
            raise AuthorizationError(missing)
        handlers = self._open_logs()
        try:
            return self._preview_live(max_records)
        finally:
            self._close_logs(handlers)

    def _preview_live(self, max_records: int) -> PreviewResult:
        extraction = self.cfg.extraction
        auth_requests = 2 if self.cfg.auth.type != "none" else 0
        ctx = self._context(self._limit_values(max_pages=1, max_records=max_records,
                                               max_requests=min(self.cfg.limits.max_requests, 2 + auth_requests),
                                               max_clicks=0, max_scrolls=0))
        adapter = create_adapter(extraction.method, ctx)
        raw: list[RawRecord] = []
        try:
            generator = adapter.iter_documents()
            try:
                doc = next(generator)
                for item in parse_document(doc, extraction).items[:max_records]:
                    raw.append(RawRecord(item, doc.final_url, doc.fetched_at, extraction.method, 0))
            finally:
                generator.close()
        except StopIteration:
            pass
        except (BarrierDetected, *POLICY_ERRORS, *TECHNICAL_ERRORS, AuthFailed, LimitReached, Cancelled) as exc:
            self._incident_from(exc, ctx, self.cfg.target_url)
        finally:
            adapter.close()
            ctx.client.close()
        records, quality = TransformPipeline(extraction).process(raw, "preview")
        result = PreviewResult(records, quality, self.cfg.target_url, ctx.budget.requests, ctx.incidents.items)
        if result.incidents:
            result.files = self._record_event(result.incidents, "vista previa", self._event_dir("vistas_previas"), ctx.actions)
        return result

    # ------------------------------------------------------------------ extracción
    def run(self, *, confirmed: bool, run_id: str | None = None) -> RunResult:
        missing = missing_for_extraction(self.cfg)
        if not confirmed:
            missing.append("Falta la confirmación explícita del usuario para iniciar solicitudes de extracción")
        if missing:
            raise AuthorizationError(missing)

        cfg, extraction = self.cfg, self.cfg.extraction
        run_id = run_id or new_run_id()
        run_dir = self.output_dir / cfg.project.name / run_id
        log_handlers = self._open_logs(run_dir / "run.log")
        self.logger.info("Inicio de ejecución %s (%s, método %s)", run_id, cfg.target_url, extraction.method)
        ctx = self._context(self._limit_values())
        result = RunResult(run_id, cfg.project.name, cfg.target_url, extraction.method, "completado",
                           "Extracción finalizada sin incidencias", utc_now_iso(), run_dir=str(run_dir))
        raw_records: list[RawRecord] = []
        adapter = None
        try:
            adapter = create_adapter(extraction.method, ctx)
            generator = adapter.iter_documents()
            try:
                for doc in generator:
                    parsed = parse_document(doc, extraction)
                    if not result.structure and parsed.structure:
                        result.structure = parsed.structure
                    ctx.last_page_records = len(parsed.items)
                    ctx.actions.record("parse", doc.final_url, f"{len(parsed.items)} registros en página {doc.page_index + 1}")
                    if not parsed.items:
                        ctx.incidents.add("empty_page", "Página sin registros con las reglas actuales (¿cambio de estructura?)",
                                          doc.final_url, "Revisar selectores con la vista previa antes de continuar.", "media")
                    for item in parsed.items:
                        if ctx.budget.records_remaining <= 0:
                            break
                        raw_records.append(RawRecord(item, doc.final_url, doc.fetched_at, extraction.method, doc.page_index))
                        ctx.budget.add_records()
                    if ctx.budget.records_remaining <= 0:
                        raise LimitReached("max_records", str(cfg.limits.max_records))
            finally:
                generator.close()
        except LimitReached as exc:
            result.status, result.status_message = "completado_con_limites", str(exc)
            self._incident_from(exc, ctx, cfg.target_url)
        except BarrierDetected as exc:
            result.status = "parcial_barrera" if raw_records else "detenido_barrera"
            result.status_message = str(exc)
            self._incident_from(exc, ctx, cfg.target_url)
        except POLICY_ERRORS as exc:
            result.status, result.status_message = "detenido_politica", str(exc)
            self._incident_from(exc, ctx, cfg.target_url)
        except AuthFailed as exc:
            result.status, result.status_message = "fallido", str(exc)
            self._incident_from(exc, ctx, cfg.target_url)
        except Cancelled as exc:
            result.status, result.status_message = "cancelado", str(exc)
            self._incident_from(exc, ctx, cfg.target_url)
        except Exception as exc:  # cualquier fallo técnico se registra y no se reintenta
            result.status, result.status_message = "fallido", f"{type(exc).__name__}: {exc}"
            result.errors.append(result.status_message)
            self._incident_from(exc, ctx, cfg.target_url)
            self.logger.error("Fallo técnico: %s", result.status_message)
        finally:
            if adapter is not None:
                adapter.close()
            ctx.client.close()

        try:
            return self._finish(result, ctx, raw_records, run_dir)
        finally:
            self._close_logs(log_handlers)

    def _finish(self, result: RunResult, ctx: AcquisitionContext, raw_records: list[RawRecord], run_dir: Path) -> RunResult:
        cfg = self.cfg
        effective_config = cfg.model_dump(mode="json", by_alias=True)
        result.config_sha256 = config_fingerprint(effective_config)
        result.tool_version = __version__
        provenance = {"config_sha256": result.config_sha256, "tool_version": result.tool_version}
        records, quality = TransformPipeline(cfg.extraction).process(raw_records, result.run_id, provenance)
        result.records, result.quality = records, quality
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "config_efectiva.json").write_text(
            json.dumps(effective_config, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        result.incidents = ctx.incidents.items
        result.budget = ctx.budget.snapshot()

        store = ProfileStore(self.output_dir / "profiles")
        profile = build_profile(cfg, result.run_id, quality, result.structure)
        previous = store.load(cfg.profile_name)
        result.profile_changes = compare_profiles(previous, profile) if previous else []
        result.requires_human_review = requires_review(result.profile_changes)
        notes = list(ctx.notes)
        if result.requires_human_review:
            ctx.incidents.add("change_detected", "Cambios relevantes frente al perfil anterior; no se corrige nada "
                              "automáticamente", cfg.target_url, "Revisión humana de selectores y alcance.", "alta")
            notes.append("La línea base del perfil NO se actualizó por requerir revisión humana.")
        elif result.status in ("completado", "completado_con_limites"):
            store.save(cfg.profile_name, profile)
            notes.append(f"Perfil '{cfg.profile_name}' actualizado como línea base.")
        else:
            notes.append("La línea base del perfil no se actualizó porque la ejecución no terminó correctamente.")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

        result.finished_at = utc_now_iso()
        summary = config_summary(cfg)
        bundle = ExportBundle(
            run_id=result.run_id, project=cfg.project.name, field_names=[f.name for f in cfg.extraction.fields],
            records=records, incidents=result.incidents,
            metadata={"target_url": cfg.target_url, "method": cfg.extraction.method, "status": result.status,
                      "config_sha256": result.config_sha256, "tool_version": result.tool_version,
                      "started_at": result.started_at, "finished_at": result.finished_at,
                      "authorization": summary["authorization"], "limits": summary["limits"],
                      "quality": quality.to_dict()},
        )
        sqlite_path = Path(cfg.output.sqlite_path) if cfg.output.sqlite_path else self.output_dir / "web_extractor.sqlite"
        result.outputs = export_all(bundle, run_dir, list(cfg.output.formats), sqlite_path)
        ctx.actions.write_jsonl(run_dir / "actions.jsonl")
        result.outputs["actions"] = str(run_dir / "actions.jsonl")
        result.outputs["log"] = str(run_dir / "run.log")
        result.outputs["profile"] = str(run_dir / "profile.json")
        result.outputs["config"] = str(run_dir / "config_efectiva.json")
        result.outputs.update(self._record_event(result.incidents, "extracción", run_dir, None))
        if "intervention" in result.outputs:
            notes.append(f"Intervención humana requerida: pasos en {result.outputs['intervention']} "
                         f"(también en {self.output_dir / 'intervenciones.jsonl'}).")
        result.next_steps = next_steps_for(result)
        result.outputs.update(write_run_report(result, run_dir, summary, notes))
        self.logger.info("Fin de ejecución %s: %s (%d registros exportados)", result.run_id, result.status, quality.exported)
        return result
