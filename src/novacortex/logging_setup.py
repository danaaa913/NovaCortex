"""Logging configuration shared by every module.

Every module does ``logger = logging.getLogger(__name__)``; this module
installs the handlers (file + console) once, when the application starts.
"""
import logging
import sys

from novacortex.config import LOG_FILE

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Install file + console handlers (idempotent)."""
    global _configured
    if _configured:
        return
    _configured = True
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
