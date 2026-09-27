import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from api.index import app


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_entrypoint_does_not_import_pyomo():
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from api.index import app; "
            "assert not any(name.startswith('pyomo') for name in sys.modules)",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert check.returncode == 0, check.stderr


def test_vercel_entrypoint_loads_verified_study():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "product": "GasOps",
        "dataset_id": "8fe7073798e19d6e",
        "offline": True,
    }


def test_vercel_config_builds_frontend_and_preserves_spa_routes():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["outputDirectory"] == "frontend/dist"
    assert config["devCommand"].startswith("npm --prefix frontend")
    assert config["functions"]["api/index.py"]["maxDuration"] == 60
    rewrites = config["rewrites"]
    assert rewrites[0] == {
        "source": "/api/:path*",
        "destination": "/api/index",
    }
    routes = {rewrite["source"] for rewrite in rewrites}
    assert {"/overview", "/model", "/optimizer", "/results", "/solver"} <= routes
