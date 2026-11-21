"""Clasificador explicable de método de adquisición.

Puntuación = base del método + suma de los pesos que aportan los hallazgos. La puntuación se
recorta a 0.95: nunca se declara certeza, porque solo se observó una respuesta. Cada
recomendación lista los indicios a favor y en contra, y requisitos pendientes. Un método que no
puede verificarse como autorizado (p. ej. una API sin documentación pública confirmada) se marca
``executable=False`` ("no verificado / no ejecutar").
"""

from __future__ import annotations

from web_extractor.config.schema import ProjectConfig
from web_extractor.models.results import Finding, MethodRecommendation

BASE_SCORES = {"static_html": 0.3, "browser": 0.1, "structured_file": 0.0, "api": 0.0}
LABELS = {"static_html": "HTML estático (Requests + BeautifulSoup)",
          "browser": "Navegador para contenido renderizado (Selenium)",
          "structured_file": "Archivo estructurado descargable (JSON/CSV)",
          "api": "API pública documentada"}


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "alta"
    if score >= 0.5:
        return "media"
    return "baja"


def _selenium_available() -> bool:
    try:
        import selenium  # noqa: F401
    except ImportError:
        return False
    from web_extractor.extractors.browser_selenium import available_browsers

    return bool(available_browsers())


def classify(findings: list[Finding], cfg: ProjectConfig) -> list[MethodRecommendation]:
    recommendations = []
    for method, base in BASE_SCORES.items():
        score = base
        reasons, against = [], []
        for finding in findings:
            weight = finding.weights.get(method, 0.0)
            if weight > 0:
                reasons.append(f"{finding.message} (+{weight:.2f})")
            elif weight < 0:
                against.append(f"{finding.message} ({weight:.2f})")
            score += weight
        executable, requirements = True, []
        if method == "api":
            api = cfg.extraction.api
            if api.documented and api.documentation_url:
                score += 0.35
                reasons.append(f"Documentación declarada por el usuario: {api.documentation_url} (+0.35)")
            else:
                executable = False
                requirements.append("No verificado / no ejecutar: falta confirmar una API pública y documentada "
                                    "(extraction.api.documented + documentation_url)")
        if method == "structured_file":
            requirements.append("Confirmar que el archivo es público, autorizado y su licencia permite el uso")
        if method == "browser":
            requirements.append("Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos")
            if not _selenium_available():
                executable = False
                requirements.append("Selenium o un navegador compatible (Chrome/Edge) no están disponibles en este entorno")
        if cfg.authorization.environment != "fixture" and not cfg.authorization.confirmed:
            requirements.append("Falta confirmar autorización antes de extraer")
        score = round(min(0.95, max(0.0, score)), 2)
        recommendations.append(MethodRecommendation(method, score, confidence_label(score), executable,
                                                    reasons, against, requirements))
    recommendations.sort(key=lambda r: (r.executable, r.score), reverse=True)
    return recommendations
