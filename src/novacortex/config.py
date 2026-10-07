"""Central configuration: paths, secrets and feature thresholds.

Secrets are read from the environment (optionally loaded from a ``.env`` file
in the working directory); see ``.env.example`` for the expected variables.
All paths are relative to the working directory - run the bot from the
project root.
"""
import os
import sys
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- paths
DATA_DIR = Path(os.getenv("NOVACORTEX_DATA_DIR", "data"))
DATA_FILE = DATA_DIR / "yarmouk_data.json"
DB_PATH = Path(os.getenv("NOVACORTEX_DB_PATH", "novacortex_v12.db"))
LOG_FILE = Path(os.getenv("NOVACORTEX_LOG_FILE", os.path.join("logs", "novacortex.log")))

# --------------------------------------------------- constants (verbatim)
CHROMA_PATH = "chroma_ultra"
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
SYNTHETIC_QUESTIONS_FILE = "synthetic_questions.json"
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

UNIVERSITY_NAME = "جامعة اليرموك"

RAG_CONFIDENCE_THRESHOLD = 0.60
CURRENT_YEAR = 2026
CURRENT_MONTH = 3

OFFICIAL_PDFS = {
    "fees_and_majors": "https://admreg.yu.edu.jo/images/docs/majors.pdf"
}
SYNTHETIC_FROZEN = True

# ---------------------------------------------------------------- secrets
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

_SECRETS = ("GROQ_API_KEY", "TELEGRAM_TOKEN", "SERPER_API_KEY")


def missing_secrets() -> List[str]:
    """Names of the secrets that are not configured."""
    return [name for name in _SECRETS if not globals()[name]]


def require_secrets() -> None:
    """Exit with a clear message when a required secret is missing."""
    missing = missing_secrets()
    if missing:
        logger.error("Missing API keys: %s - copy .env.example to .env and fill it in.",
                     ", ".join(missing))
        sys.exit(1)
