import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from api.index import app
from gasopt.data.processed import json_hash


ROOT = Path(__file__).resolve().parents[1]


def test_json_identity_is_platform_independent(tmp_path):
    content = '{\n  "name": "GasOps",\n  "version": 1\n}\n'
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(content.encode("utf-8"))
    crlf.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))
    assert json_hash(lf) == json_hash(crlf)
    assert json_hash(ROOT / "data/processed/metadata.json") == json.loads(
        (ROOT / "outputs/empirical/study_metadata.json").read_text(encoding="utf-8")
    )["processed_metadata_sha256"]


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
        "dataset_id": "527fa244aeb073b8",
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
