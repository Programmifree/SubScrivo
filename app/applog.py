"""applog.py - Log tecnico su file, senza contenuto delle trascrizioni.

Regole:
  * non viene mai registrato il testo trascritto;
  * non vengono registrati i percorsi completi dei file dell'utente
    (solo il nome file, e solo per eventi tecnici);
  * i log restano nella cartella portabile work/logs.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import portable

_LOGGER_NAME = "subscrivo"
_configured = False


def _sanitize(value: str, limit: int = 500) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ")
    text = text.encode("utf-8", "replace").decode("utf-8")
    if len(text) > limit:
        text = text[:limit] + "...[troncato]"
    return text


def setup(level: int = logging.INFO) -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    try:
        portable.LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            portable.LOG_DIR / "subscrivo.log",
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    except Exception:
        pass

    _configured = True
    return logger


def get() -> logging.Logger:
    return setup()


def log_error(context: str, exc: BaseException) -> None:
    logger = get()
    logger.error("%s: %s: %s", context, type(exc).__name__, _sanitize(exc))