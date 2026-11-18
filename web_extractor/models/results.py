"""Estructuras de resultados: documentos, hallazgos, incidencias, registros y ejecuciones."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from web_extractor.utils.timeutils import utc_now_iso


@dataclass
class FetchedDocument:
    """Respuesta obtenida de forma autorizada (HTTP o navegador)."""

    url: str
    final_url: str
    status: int
    content_type: str
    text: str
    fetched_at: str = field(default_factory=utc_now_iso)
    headers: dict[str, str] = field(default_factory=dict)
    via: str = "http"
    page_index: int = 0
    truncated: bool = False

    @property
    def is_json(self) -> bool:
        return "json" in self.content_type

    @property
    def is_csv(self) -> bool:
        return "csv" in self.content_type

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type or (not self.is_json and not self.is_csv)


@dataclass
class Finding:
    """Indicio observado durante el diagnóstico.

    ``weights`` expresa cuánto apoya (positivo) o contradice (negativo) cada método; el
    clasificador solo suma estos pesos, de modo que cada recomendación es explicable.
    """

    code: str
    category: str
    message: str
    evidence: str = ""
    weights: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MethodRecommendation:
    method: str
    score: float
    confidence: str
    executable: bool
    reasons: list[str] = field(default_factory=list)
    against: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Incident:
    """Evento que detiene o degrada un flujo y requiere atención humana."""

    kind: str
    message: str
    url: str = ""
    next_step: str = ""
    severity: str = "alta"
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Diagnosis:
    target_url: str
    final_url: str = ""
    status_code: int | None = None
    content_type: str = ""
    fetched_at: str = field(default_factory=utc_now_iso)
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[MethodRecommendation] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    incidents: list[Incident] = field(default_factory=list)
    candidates: dict[str, Any] = field(default_factory=dict)
    requests_used: int = 0
    stopped: bool = False

    @property
    def best(self) -> MethodRecommendation | None:
        executable = [r for r in self.recommendations if r.executable]
        return executable[0] if executable else None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParseResult:
    """Registros crudos de un documento y una firma de su estructura (para detectar cambios)."""

    items: list[dict[str, Any]]
    structure: list[str] = field(default_factory=list)


@dataclass
class RawRecord:
    values: dict[str, Any]
    source_url: str
    retrieved_at: str
    method: str
    page_index: int = 0


@dataclass
class ProcessedRecord:
    data: dict[str, Any]
    raw: dict[str, Any]
    lineage: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"data": self.data, "raw": self.raw, "lineage": self.lineage}


@dataclass
class FieldQuality:
    filled: int = 0
    empty: int = 0
    invalid: int = 0

    def fill_rate(self, total: int) -> float:
        return round(self.filled / total, 4) if total else 0.0


@dataclass
class QualityReport:
    total_raw: int = 0
    valid: int = 0
    with_warnings: int = 0
    invalid: int = 0
    duplicates_removed: int = 0
    dropped_invalid: int = 0
    exported: int = 0
    fields: dict[str, FieldQuality] = field(default_factory=dict)
    error_samples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        total = self.total_raw
        for name, quality in self.fields.items():
            data["fields"][name]["fill_rate"] = quality.fill_rate(total)
        return data


@dataclass
class PreviewResult:
    records: list[ProcessedRecord]
    quality: QualityReport
    source: str
    requests_used: int = 0
    incidents: list[Incident] = field(default_factory=list)


@dataclass
class RunResult:
    run_id: str
    project: str
    target_url: str
    method: str
    status: str
    status_message: str
    started_at: str
    finished_at: str = ""
    budget: dict[str, Any] = field(default_factory=dict)
    records: list[ProcessedRecord] = field(default_factory=list)
    quality: QualityReport = field(default_factory=QualityReport)
    incidents: list[Incident] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    profile_changes: list[dict[str, Any]] = field(default_factory=list)
    requires_human_review: bool = False
    next_steps: list[str] = field(default_factory=list)
    structure: list[str] = field(default_factory=list)
    run_dir: str = ""
    config_sha256: str = ""
    tool_version: str = ""

    def summary_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project": self.project,
            "config_sha256": self.config_sha256,
            "tool_version": self.tool_version,
            "target_url": self.target_url,
            "method": self.method,
            "status": self.status,
            "status_message": self.status_message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "budget": self.budget,
            "quality": self.quality.to_dict(),
            "incidents": [i.to_dict() for i in self.incidents],
            "errors": self.errors,
            "outputs": self.outputs,
            "profile_changes": self.profile_changes,
            "requires_human_review": self.requires_human_review,
            "next_steps": self.next_steps,
            "structure": self.structure,
        }
