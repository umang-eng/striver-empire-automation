"""Unit tests for the FastAPI backend API, job store, and validation."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import create_app


def _make_client(tmp_path) -> TestClient:
    app = create_app(
        config_path="config/settings.json",
        database_url="",
        sqlite_path=str(tmp_path / "test_jobs.db"),
    )
    return TestClient(app)


def test_health_and_categories_endpoints(tmp_path):
    client = _make_client(tmp_path)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    cats = client.get("/api/categories")
    assert cats.status_code == 200
    groups = cats.json()["groups"]
    ids = [g["id"] for g in groups]
    assert ids == [
        "mens",
        "womens",
        "beauty-and-cosmetics",
        "accessories",
        "winter",
        "home-living",
    ]


def test_create_task_validation_and_deduplication(tmp_path):
    client = _make_client(tmp_path)

    # Reject invalid messages
    bad1 = client.post("/api/tasks", json={"message": "women 100%"})
    assert bad1.status_code == 422
    bad2 = client.post("/api/tasks", json={"message": "25%"})
    assert bad2.status_code == 422

    # Mock worker execution so unit test does not launch live browser
    with patch("backend.worker.TaskRunner._execute_job", return_value=None):
        res1 = client.post("/api/tasks", json={"message": "women 25%"})
        assert res1.status_code == 202
        data1 = res1.json()
        assert data1["category"] == "Women"
        assert data1["discount_percent"] == "25"
        assert data1["status"] == "queued"
        assert data1["deduplicated"] is False

        # Duplicate concurrent submission returns existing active job
        res2 = client.post("/api/tasks", json={"message": "women 25%"})
        assert res2.status_code == 202
        data2 = res2.json()
        assert data2["task_id"] == data1["task_id"]
        assert data2["deduplicated"] is True

        # Status & progress lookup
        prog = client.get(f"/api/tasks/{data1['task_id']}/progress")
        assert prog.status_code == 200
        assert prog.json()["stage"] == "Validating task"

        # Delete cleans up job
        deleted = client.delete(f"/api/tasks/{data1['task_id']}")
        assert deleted.status_code == 200
        assert client.get(f"/api/tasks/{data1['task_id']}").status_code == 404


def test_invalid_task_id_rejected(tmp_path):
    client = _make_client(tmp_path)
    res = client.get("/api/tasks/../../etc/passwd")
    assert res.status_code in (400, 404)
    res2 = client.get("/api/tasks/not-a-uuid")
    assert res2.status_code == 400
