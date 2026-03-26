import pytest
from app.main import create_app, db as _db


@pytest.fixture()
def client():
    application = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
    })
    with application.test_client() as c:
        yield c


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json["status"] == "ready"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json["status"] == "healthy"


def test_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"http_requests_total" in resp.data


def test_create_run(client):
    resp = client.post("/api/runs", json={"sample_id": "SAMPLE-001"})
    assert resp.status_code == 201
    assert resp.json["sample_id"] == "SAMPLE-001"
    assert resp.json["status"] == "queued"


def test_create_run_missing_sample_id(client):
    resp = client.post("/api/runs", json={})
    assert resp.status_code == 400


def test_get_run(client):
    create = client.post("/api/runs", json={"sample_id": "SAMPLE-002"})
    run_id = create.json["id"]
    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json["sample_id"] == "SAMPLE-002"


def test_update_run(client):
    create = client.post("/api/runs", json={"sample_id": "SAMPLE-003"})
    run_id = create.json["id"]
    resp = client.patch(
        f"/api/runs/{run_id}",
        json={"status": "completed", "duration": 42.5},
    )
    assert resp.status_code == 200
    assert resp.json["status"] == "completed"
    assert resp.json["duration"] == 42.5


def test_list_runs(client):
    client.post("/api/runs", json={"sample_id": "A"})
    client.post("/api/runs", json={"sample_id": "B"})
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert len(resp.json) == 2


def test_list_runs_filter(client):
    client.post("/api/runs", json={"sample_id": "A"})
    create = client.post("/api/runs", json={"sample_id": "B"})
    client.patch(f"/api/runs/{create.json['id']}", json={"status": "completed"})
    resp = client.get("/api/runs?status=completed")
    assert resp.status_code == 200
    assert len(resp.json) == 1
    assert resp.json[0]["status"] == "completed"


def test_get_run_not_found(client):
    resp = client.get("/api/runs/9999")
    assert resp.status_code == 404
