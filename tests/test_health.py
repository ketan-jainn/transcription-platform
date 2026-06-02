from fastapi.testclient import TestClient
from src.api.main import app


def test_live():
    client = TestClient(app)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
