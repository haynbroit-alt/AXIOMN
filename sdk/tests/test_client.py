"""Tests the SDK against the real AXIOMN FastAPI app running on loopback —
this is exactly how the SDK is used in practice, just pointed at localhost
instead of a hosted deployment."""
from axiomn_sdk import AXIOMNClient


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
