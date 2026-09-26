"""Vercel ASGI entrypoint for the versioned GasOps API."""

from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
os.environ.setdefault("GASOPS_ROOT", str(PROJECT_ROOT))

from gasopt.api.main import app  # noqa: E402,F401
