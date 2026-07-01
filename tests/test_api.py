from fastapi.testclient import TestClient

from axiomn.api.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_intent_endpoint_returns_full_pipeline_result():
    response = client.post("/intent", json={"text": "Explain how black holes form"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "learn"
    assert data["route"] in {"local_ai", "cloud_ai", "human_queue"}
    assert data["result"]


def test_intent_endpoint_rejects_missing_text():
    response = client.post("/intent", json={})
    assert response.status_code == 422
