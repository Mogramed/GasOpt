import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.index import app


ROOT = Path(__file__).resolve().parents[1]


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
    assert config["functions"]["api/index.py"]["maxDuration"] == 60
    routes = {rewrite["source"] for rewrite in config["rewrites"]}
    assert {"/overview", "/model", "/optimizer", "/results", "/solver"} <= routes
