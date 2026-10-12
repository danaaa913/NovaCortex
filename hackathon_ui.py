"""Launch the optional Streamlit interface without installing the package."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from hackathon_rag.ui import main  # noqa: E402


main()
