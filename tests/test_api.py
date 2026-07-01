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
    assert data["tool"]
    assert data["execution_time_ms"] >= 0
    assert 0.0 <= data["ambiguity"] <= 1.0
    assert data["action"]["type"] == "voice_reply"
    assert data["action"]["payload"]["text"] == data["result"]


def test_connect_intent_escalates_to_human_and_yields_await_human_action():
    # CONNECT always routes to human_queue, which overrides the category's
    # usual action mapping (open_url) with await_human — there's no
    # instant answer to hand back yet.
    response = client.post("/intent", json={"text": "Trouve un expert en droit fiscal pour moi"})
    data = response.json()
    assert data["route"] == "human_queue"
    assert data["action"]["type"] == "await_human"


def test_intent_endpoint_rejects_missing_text():
    response = client.post("/intent", json={})
    assert response.status_code == 422
