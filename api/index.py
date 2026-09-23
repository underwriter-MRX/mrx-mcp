"""Vercel ASGI entrypoint; the standalone CLI remains available."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mrx_mcp.http import create_app

app = create_app()
