"""The `/v1` prefix is the stable contract; bare paths stay as compatibility
aliases. Both must serve the same behavior, and the schema only advertises
v1 — that's what "versioned" means: one documented contract, no silent
second one."""
from fastapi.testclient import TestClient

from axiomn.api.main import app

client = TestClient(app)


def test_v1_intent_serves_the_full_pipeline():
    response = client.post("/v1/intent", json={"text": "Explain how black holes form"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "learn"
    assert data["action"]["type"] == "voice_reply"


def test_unversioned_paths_remain_as_compatible_aliases():
    v1 = client.post("/v1/intent", json={"text": "Explain how black holes form"}).json()
    legacy = client.post("/intent", json={"text": "Explain how black holes form"}).json()
    # Identical contract: same fields, same classification, same routing.
    assert set(v1) == set(legacy)
    assert (v1["intent"], v1["route"], v1["tool"]) == (
        legacy["intent"],
        legacy["route"],
        legacy["tool"],
    )
    assert client.get("/v1/health").json() == client.get("/health").json()


def test_v1_queue_round_trip():
    payload = client.post(
        "/v1/intent", json={"text": "Trouve un expert en droit fiscal pour moi"}
    ).json()["action"]["payload"]
    ticket_id = payload["ticket_id"]

    assert client.get(f"/v1/queue/{ticket_id}").json()["status"] == "pending"
    client.post(f"/v1/queue/{ticket_id}/answer", json={"text": "Voici."})
    assert client.get(f"/v1/queue/{ticket_id}").json()["status"] == "answered"


def test_metrics_reflect_traffic():
    before = client.get("/v1/metrics").json()["requests"].get("total", 0)

    client.post("/v1/intent", json={"text": "Explain how black holes form"})
    client.post("/v1/intent", json={"text": "Trouve un expert en droit fiscal pour moi"})

    snap = client.get("/v1/metrics").json()
    assert snap["requests"]["total"] == before + 2
    assert snap["requests"]["success_rate"] > 0
    # Route shares are a distribution over all traffic so far.
    assert abs(sum(r["share"] for r in snap["routes"].values()) - 1.0) < 0.01
    assert snap["latency_ms"]["p95"] >= snap["latency_ms"]["p50"] >= 0
    assert snap["cost"]["avg_per_request"] >= 0


def test_openapi_schema_only_documents_v1():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/intent" in paths
    assert "/v1/metrics" in paths
    assert "/intent" not in paths
    assert "/metrics" not in paths
