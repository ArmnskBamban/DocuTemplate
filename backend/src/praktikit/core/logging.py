"""Structured logging setup.

Privacy is enforced by design (spec Section 11 / Section 68): only operational
metadata (session id, file size, counts, stage, duration, errors) is ever
logged. Document body text, names, NIMs and other personal content must never
appear in log records. Callers should log *counts and IDs*, never content.
"""

from __future__ import annotations

import logging
from typing import Any

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once.

    A simple ``levelname: name: message`` format is used (no colors) so logs
    are greppable and safe to ship anywhere. Re-calls are idempotent.
    """
    global _CONFIGURED
    if _CONFIGURED and level is None:
        return

    from praktikit.core.config import get_settings

    log_level = (level or get_settings().log_level or "INFO").upper()
    root = logging.getLogger("praktikit")
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        _CONFIGURED = True
    root.setLevel(getattr(logging, log_level, logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``praktikit`` namespace."""
    return logging.getLogger(f"praktikit.{name}")


def safe_log(logger: logging.Logger, level: int, msg: str, **kwargs: Any) -> None:
    """Log only non-sensitive metadata.

    This is a thin guardrail: it logs the message and the provided keyword
    metadata, which the caller is responsible for keeping free of personal data
    (counts, ids, durations, sizes — never text content).
    """
    logger.log(level, msg, extra={"metadata": kwargs})
