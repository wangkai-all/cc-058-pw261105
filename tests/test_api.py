"""Black-box API tests against the real FastAPI app and seeded SQLite."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("PLANNER_DB", tmp.name)
    # reload db module so DB_PATH picks up the env var
    import importlib

    from app import db as db_mod
    importlib.reload(db_mod)
    from app import main as main_mod
    importlib.reload(main_mod)
    main_mod._startup()
    with TestClient(main_mod.app) as c:
        yield c
    os.unlink(tmp.name)


def test_health_and_seeded_catalog(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    boxes = client.get("/api/box-types").json()
    plans = client.get("/api/freight-plans").json()
    assert len(boxes) >= 4 and len(plans) >= 3
    for b in boxes:
        assert b["inner_l"] <= b["outer_l"]


def test_solve_endpoint_happy_path(client):
    payload = {"items": [
        {"sku": "A", "l": 120, "w": 100, "h": 80, "weight_g": 700,
         "orientation": "any", "qty": 4},
        {"sku": "B", "l": 50, "w": 50, "h": 180, "weight_g": 250,
         "orientation": "upright", "qty": 3},
    ]}
    r = client.post("/api/solve", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["validator_passed"], data["validator_errors"]
    assert data["unpacked"] == []
    assert data["cheapest_freight_plan_code"] in {"STD", "ECON", "AIR"}
    for q in data["quotes"]:
        assert q["total_fee"] == pytest.approx(
            round(q["total_freight"] + q["total_box_fee"], 4)
        )


def test_solve_oversize_returns_exceeds_all_boxes(client):
    payload = {"items": [
        {"sku": "HUGE", "l": 9000, "w": 9000, "h": 9000, "weight_g": 100,
         "orientation": "any", "qty": 2},
    ]}
    data = client.post("/api/solve", json=payload).json()
    assert data["feasible"] is False
    assert data["unpacked"][0]["reason"] == "exceeds_all_boxes"
    assert data["unpacked"][0]["qty"] == 2


def test_create_box_type_validation(client):
    r = client.post("/api/box-types", json={
        "code": "X1", "inner_l": 0, "inner_w": 1, "inner_h": 1,
        "outer_l": 1, "outer_w": 1, "outer_h": 1,
        "box_weight_g": 10, "box_fee": 1.0, "max_gross_g": 100,
    })
    assert r.status_code == 422


def test_solve_run_persisted(client):
    from app import db as db_mod
    payload = {"items": [
        {"sku": "A", "l": 100, "w": 100, "h": 100, "weight_g": 500,
         "orientation": "any", "qty": 1},
    ]}
    client.post("/api/solve", json=payload)
    with db_mod.get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM solve_runs").fetchone()[0]
    assert n == 1
