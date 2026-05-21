"""Centralized logging setup.

Why a dedicated module: we need consistent log format across services, a
rotating file handler for the cost-tracking log, and the ability to bump
the level via env var without touching code.
"""

import logging
import logging.handlers
import os
from pathlib import Path

from app.config import get_settings


def configure_logging() -> None:
    """Configure root logger. Call once at app startup.

    Adds a stream handler for stdout (so Docker logs show output) and a
    rotating file handler for persistent local logs.
    """
    settings = get_settings()
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    # Avoid duplicate handlers when uvicorn reloads.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)

    if not any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers
    ):
        try:
            rotating = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            rotating.setFormatter(fmt)
            root.addHandler(rotating)
        except OSError:
            # If the log path isn't writable (e.g. running tests outside
            # Docker), continue without the file handler instead of crashing.
            root.warning("Could not open log file %s; continuing with stdout only.", log_path)

    # Quiet noisy libraries.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper. `from app.logging_config import get_logger`."""
    return logging.getLogger(name)
