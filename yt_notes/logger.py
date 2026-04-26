"""
logger.py
=========
Configures application-wide logging with:
  - Rich console handler (colour, tracebacks)
  - Rotating file handler  → logs/yt_notes.log  (max 5 MB × 3 files)

Usage::

    from yt_notes.logger import get_logger
    log = get_logger(__name__)
    log.info("Fetching transcript for %s", video_id)
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

from yt_notes.config import settings

_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "yt_notes.log"
_INITIALISED = False


def _setup() -> None:
    """One-time logging initialisation called on first ``get_logger`` call."""
    global _INITIALISED
    if _INITIALISED:
        return

    _LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(settings.log_level)

    # Rich console handler — pretty, with syntax highlighting
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=False,
        markup=True,
    )
    console_handler.setLevel(settings.log_level)

    # Rotating file handler — plain text for grep/analysis
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # always verbose in file
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _INITIALISED = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger, initialising the logging system on first call.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    _setup()
    return logging.getLogger(name)
