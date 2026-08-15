from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_graph_empty_by_default():
    res = client.get("/graph")
    assert res.status_code == 200
    body = res.json()
    assert body["nodes"] == []
    assert body["edges"] == []