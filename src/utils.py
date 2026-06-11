"""Shared helpers: logging setup and small reusable utilities."""

import logging

import config


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger wired to the project-wide format.

    Configured once at the root level so every stage emits aligned,
    timestamped lines that read like a pipeline run log.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=config.LOG_LEVEL,
            format=config.LOG_FORMAT,
            datefmt=config.LOG_DATEFMT,
        )
    return logging.getLogger(name)


def fmt_int(n: int) -> str:
    """Format an integer with thousands separators (e.g. 180519 -> 180,519)."""
    return f"{n:,}"
