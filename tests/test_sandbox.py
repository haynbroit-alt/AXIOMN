"""The VERITY sandbox handler exercised against a mock HTTP transport: the
request shape AXIOMN sends to `/v1/verify`, how a signed proof is surfaced in
`ToolResult.metadata`, and — critically — that the integration is opt-in and
fail-open, so a runtime with no sandbox configured (or an unreachable one)
behaves exactly as it did before this wiring existed.
"""
import json

import httpx
import pytest

from axiomn.intent.schema import Intent, IntentCategory
from axiomn.models.tools import default_registry
from axiomn.router.router import Route
from axiomn.sandbox import VeritySandboxHandler, build_verity_handler


def _intent(text: str = "print(2 ** 10)") -> Intent:
    return Intent(
        text=text,
        category=IntentCategory.AUTOMATE,
        topic=text,
        language="en",
        difficulty=4,
        confidence=0.9,
    )


def _verity_ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "action_id": "act-123",
            "status": "COMPLETED",
            "execution": {"stdout": "1024\n", "exit_code": 0, "execution_time_ms": 12.5},
            "verification": {"passed": True, "security_flags": [], "violations": []},
            "proof": {"signature": "ed25519:deadbeef"},
        },
    )


def test_handler_sends_intent_text_as_sandbox_payload():
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return _verity_ok_response(request)

    handler = VeritySandboxHandler(
        "https://verity.example", transport=httpx.MockTransport(responder)
    )
    result = handler.run(_intent("print(2 ** 10)"))
    handler.close()

    assert seen["url"] == "https://verity.example/v1/verify"
    assert seen["payload"]["payload"] == "print(2 ** 10)"
    assert seen["payload"]["constraints"]["language"] == "python"
    assert seen["payload"]["agent_id"] == "axiomn-executor"


def test_signed_proof_travels_in_metadata():
    handler = VeritySandboxHandler(
        "https://verity.example", transport=httpx.MockTransport(_verity_ok_response)
    )
    result = handler.run(_intent())
    handler.close()

    assert result.success is True
    assert result.output == "1024\n"
    verity = result.metadata["verity"]
    assert verity["available"] is True
    assert verity["verified"] is True
    assert verity["action_id"] == "act-123"
    assert verity["signature"] == "ed25519:deadbeef"


def test_failed_verification_is_reported_as_failure():
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "action_id": "act-9",
                "status": "COMPLETED",
                "execution": {"stdout": "", "exit_code": 1, "execution_time_ms": 3.0},
                "verification": {
                    "passed": False,
                    "security_flags": ["network_attempt"],
                    "violations": ["exit_code != 0"],
                },
                "proof": {"signature": "ed25519:abc"},
            },
        )

    handler = VeritySandboxHandler(
        "https://verity.example", transport=httpx.MockTransport(responder)
    )
    result = handler.run(_intent())
    handler.close()

    # A signed proof of a *failed* run is still a failure the Router must learn.
    assert result.success is False
    assert result.metadata["verity"]["security_flags"] == ["network_attempt"]


def test_handler_fails_open_when_sandbox_unreachable():
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    handler = VeritySandboxHandler(
        "https://verity.example", transport=httpx.MockTransport(responder)
    )
    result = handler.run(_intent())
    handler.close()

    # Fail-open: no exception escapes; the runtime stays up and the Router is
    # told the route degraded.
    assert result.success is False
    assert result.metadata["verity"]["available"] is False
    assert "sandbox-unavailable" in result.output


def test_build_returns_none_without_config(monkeypatch):
    monkeypatch.delenv("AXIOMN_VERITY_URL", raising=False)
    assert build_verity_handler() is None


def test_build_reads_env(monkeypatch):
    monkeypatch.setenv("AXIOMN_VERITY_URL", "https://verity.example")
    handler = build_verity_handler()
    assert isinstance(handler, VeritySandboxHandler)
    assert handler.base_url == "https://verity.example"
    handler.close()


def test_registry_omits_sandbox_by_default():
    """No sandbox_handler -> AUTOMATE stays on the local heuristic, unchanged."""
    registry = default_registry()
    tool = registry.best_for(Route.LOCAL_AI, _intent())
    assert tool.name == "local_heuristic"


def test_registry_routes_automate_to_sandbox_when_configured():
    handler = VeritySandboxHandler(
        "https://verity.example", transport=httpx.MockTransport(_verity_ok_response)
    )
    registry = default_registry(sandbox_handler=handler)

    automate_tool = registry.best_for(Route.LOCAL_AI, _intent())
    assert automate_tool.name == "verity_sandbox"

    # Non-AUTOMATE local intents are untouched: still the heuristic.
    learn = Intent(
        text="explain recursion",
        category=IntentCategory.LEARN,
        topic="recursion",
        language="en",
        difficulty=3,
        confidence=0.9,
    )
    assert registry.best_for(Route.LOCAL_AI, learn).name == "local_heuristic"
    handler.close()
