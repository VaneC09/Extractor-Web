"""Adaptadores de adquisición intercambiables detrás de una interfaz común."""

from web_extractor.extractors.base import AcquisitionContext, Adapter
from web_extractor.extractors.registry import available_methods, create_adapter

__all__ = ["AcquisitionContext", "Adapter", "available_methods", "create_adapter"]
