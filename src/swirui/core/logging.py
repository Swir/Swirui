"""Logging helpers for SwirUI."""

from __future__ import annotations

import logging

LOGGER_NAME = "swirui"


def get_logger(name: str | None = None) -> logging.Logger:
    suffix = f".{name}" if name else ""
    return logging.getLogger(f"{LOGGER_NAME}{suffix}")


def configure_logging(*, debug: bool = False) -> logging.Logger:
    """Configure the SwirUI logger without mutating the root logger."""

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)

    logger.propagate = False
    return logger
