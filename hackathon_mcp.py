"""Run the optional MCP server for the local hackathon assistant."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hackathon_rag.mcp_server import run_server  # noqa: E402


if __name__ == "__main__":
    run_server()
