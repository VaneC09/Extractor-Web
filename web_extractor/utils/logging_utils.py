"""Configuración de logging con filtro de redacción obligatorio en todos los handlers."""

from __future__ import annotations

import logging
from pathlib import Path

from web_extractor.utils.redaction import redact

LOGGER_NAME = "web_extractor"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class RedactingFilter(logging.Filter):
    """Reescribe el mensaje ya formateado aplicando ``redact`` antes de emitirlo."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = redact(message)
        record.args = None
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configura el logger raíz del paquete con salida a consola (stderr)."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    for handler in list(logger.handlers):
        if getattr(handler, "_web_extractor_console", False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT, "%H:%M:%S"))
    handler.addFilter(RedactingFilter())
    handler._web_extractor_console = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def add_file_handler(path: Path) -> logging.Handler:
    """Añade un log de fichero por ejecución; el llamador debe retirarlo con ``remove_handler``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger(LOGGER_NAME)
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler


def remove_handler(handler: logging.Handler) -> None:
    logging.getLogger(LOGGER_NAME).removeHandler(handler)
    handler.close()
