"""Inspección pasiva de una respuesta autorizada y clasificación heurística del método."""

from web_extractor.inspectors.base import Inspector, run_inspectors
from web_extractor.inspectors.classifier import classify

__all__ = ["Inspector", "classify", "run_inspectors"]
