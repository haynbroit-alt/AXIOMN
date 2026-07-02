"""The full async round trip through the API: an intent escalates to a
human, the client gets a ticket, an operator answers it, and the client's
poll returns the human's answer. This is the guarantee that `await_human`
now points at a real delivery mechanism, not a dead end."""
from fastapi.testclient import TestClient

from axiomn.api.main import app

client = TestClient(app)

CONNECT_TEXT = "Trouve un expert en droit fiscal pour moi"


def _escalate() -> dict:
    data = client.post("/intent", json={"text": CONNECT_TEXT}).json()
    assert data["action"]["type"] == "await_human"
    return data


def test_escalated_intent_carries_ticket_id_and_status_url():
    payload = _escalate()["action"]["payload"]
    assert payload["ticket_id"]
    assert payload["status_url"] == f"/queue/{payload['ticket_id']}"


def test_ticket_is_pending_until_a_human_answers():
    payload = _escalate()["action"]["payload"]

    ticket = client.get(payload["status_url"]).json()
    assert ticket["status"] == "pending"
    assert ticket["question"] == CONNECT_TEXT
    assert ticket["answer"] is None


def test_full_round_trip_operator_answer_reaches_the_polling_client():
    payload = _escalate()["action"]["payload"]
    ticket_id = payload["ticket_id"]

    # The operator's worklist shows the pending ticket.
    pending_ids = [t["ticket_id"] for t in client.get("/queue").json()]
    assert ticket_id in pending_ids

    # A human answers it.
    answered = client.post(
        f"/queue/{ticket_id}/answer",
        json={"text": "Maître Dupont est spécialisée en droit fiscal."},
    )
    assert answered.status_code == 200

    # The client's next poll gets the human's answer.
    ticket = client.get(f"/queue/{ticket_id}").json()
    assert ticket["status"] == "answered"
    assert ticket["answer"] == "Maître Dupont est spécialisée en droit fiscal."
    assert ticket["answered_at"] is not None

    # And it left the operator's worklist.
    assert ticket_id not in [t["ticket_id"] for t in client.get("/queue").json()]


def test_unknown_ticket_returns_404():
    assert client.get("/queue/does-not-exist").status_code == 404
    assert (
        client.post("/queue/does-not-exist/answer", json={"text": "hi"}).status_code == 404
    )


def test_answering_twice_returns_409():
    ticket_id = _escalate()["action"]["payload"]["ticket_id"]
    client.post(f"/queue/{ticket_id}/answer", json={"text": "first"})

    second = client.post(f"/queue/{ticket_id}/answer", json={"text": "second"})
    assert second.status_code == 409
    # The first answer stands.
    assert client.get(f"/queue/{ticket_id}").json()["answer"] == "first"
