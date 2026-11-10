"""Modelos de datos (dataclasses) compartidos entre módulos."""

from web_extractor.models.results import (
    Diagnosis,
    FetchedDocument,
    FieldQuality,
    Finding,
    Incident,
    MethodRecommendation,
    ParseResult,
    PreviewResult,
    ProcessedRecord,
    QualityReport,
    RawRecord,
    RunResult,
)

__all__ = [
    "Diagnosis",
    "FetchedDocument",
    "FieldQuality",
    "Finding",
    "Incident",
    "MethodRecommendation",
    "ParseResult",
    "PreviewResult",
    "ProcessedRecord",
    "QualityReport",
    "RawRecord",
    "RunResult",
]
