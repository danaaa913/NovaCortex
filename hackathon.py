"""Zero-install-path entry point for the local hackathon RAG package."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from hackathon_rag.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
