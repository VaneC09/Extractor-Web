"""Puertas de autorización.

La herramienta **no puede verificar** que exista permiso real: solo comprueba que una persona lo
haya declarado de forma completa en la configuración y que confirme explícitamente antes de
generar solicitudes de extracción. Si falta algo, el trabajo se limita a diagnóstico o fixtures.
"""

from __future__ import annotations

from datetime import date

from web_extractor.config.schema import ProjectConfig


def missing_for_diagnosis(cfg: ProjectConfig) -> list[str]:
    a = cfg.authorization
    missing: list[str] = []
    if a.environment != "fixture" and not (a.confirmed or a.authorized_by):
        missing.append(
            "Para diagnosticar un sitio no controlado indique authorization.authorized_by "
            "(quién permite la inspección) o confirme la autorización."
        )
    if a.valid_until and a.valid_until < date.today():
        missing.append(f"La autorización expiró el {a.valid_until}")
    return missing


def missing_for_extraction(cfg: ProjectConfig) -> list[str]:
    a = cfg.authorization
    missing = missing_for_diagnosis(cfg)
    if not a.confirmed:
        missing.append("authorization.confirmed debe ser true (confirmación humana de permiso y alcance)")
    if not a.authorized_by:
        missing.append("authorization.authorized_by: indique quién autoriza la extracción")
    if not a.purpose:
        missing.append("authorization.purpose: describa la finalidad del uso de los datos")
    if not a.terms_reviewed:
        missing.append("authorization.terms_reviewed: confirme que revisó términos y políticas del sitio")
    if a.environment == "production" and not a.evidence_reference:
        missing.append("authorization.evidence_reference: referencia al permiso (correo, contrato, ticket)")
    method = cfg.extraction.method
    if method == "auto":
        missing.append("extraction.method: elija un método explícito tras revisar el diagnóstico")
    if method == "api" and not (cfg.extraction.api.documented and cfg.extraction.api.documentation_url):
        missing.append(
            "API no verificada como pública y documentada (extraction.api.documented + documentation_url): "
            "no ejecutar"
        )
    if cfg.auth.type != "none" and not a.allow_authentication:
        missing.append("authorization.allow_authentication debe ser true para usar credenciales")
    return missing
