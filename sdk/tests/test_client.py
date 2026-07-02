"""Tests the SDK against the real AXIOMN FastAPI app running on loopback —
this is exactly how the SDK is used in practice, just pointed at localhost
instead of a hosted deployment."""
import threading

import pytest

from axiomn_sdk import AXIOMNClient, HumanAnswerTimeout


def test_intent_call_returns_structured_result(live_server_url):
    with AXIOMNClient(base_url=live_server_url) as client:
        result = client.intent("Explain how black holes form")
        assert result.intent == "learn"
        assert result.route in {"local_ai", "cloud_ai", "human_queue"}
        assert result.result
        assert result.execution_time_ms >= 0
        assert result.action.type == "voice_reply"
        assert result.action.payload["text"] == result.result


def test_context_manager_classifies_french_input(live_server_url):
    with AXIOMNClient(base_url=live_server_url) as client:
        result = client.intent("Aide-moi à résoudre ce bug")
        assert result.intent == "solve"
        assert result.language == "fr"


def test_wait_for_human_returns_the_answer_a_human_gives_later(live_server_url):
    # The full async round trip, over real HTTP: escalate, block on the
    # ticket, have "a human" (another thread, via the operator API) answer
    # it mid-wait, and receive that answer.
    with AXIOMNClient(base_url=live_server_url) as client:
        result = client.intent("Trouve un expert en droit fiscal pour moi")
        assert result.action.type == "await_human"
        ticket_id = result.action.payload["ticket_id"]

        def human_answers_after_a_moment():
            with AXIOMNClient(base_url=live_server_url) as operator:
                operator.answer_ticket(ticket_id, "Contactez Maître Dupont.")

        timer = threading.Timer(0.3, human_answers_after_a_moment)
        timer.start()
        try:
            ticket = client.wait_for_human(ticket_id, timeout=10.0, poll_interval=0.1)
        finally:
            timer.join()

        assert ticket.status == "answered"
        assert ticket.answer == "Contactez Maître Dupont."


def test_wait_for_human_times_out_when_nobody_answers(live_server_url):
    with AXIOMNClient(base_url=live_server_url) as client:
        result = client.intent("Trouve un expert en droit fiscal pour moi")
        ticket_id = result.action.payload["ticket_id"]

        with pytest.raises(HumanAnswerTimeout):
            client.wait_for_human(ticket_id, timeout=0.3, poll_interval=0.1)
