"""The local tier made real: a local, OpenAI-compatible model answers the cheap
tier instead of a stub. Opt-in, fail-open, and — critically — its output is a
real answer the quality proxy no longer scores as a placeholder.
"""
import json

import httpx

from axiomn.intent.schema import Intent, IntentCategory
from axiomn.local import LocalModelHandler, build_local_handler
from axiomn.models.tools import default_registry
from axiomn.quality import assess_quality
from axiomn.router.router import Route


def _intent(text: str = "Quelle est la capitale de l'Espagne ?") -> Intent:
    return Intent(
        text=text, category=IntentCategory.LEARN, topic="x", language="fr",
        difficulty=1, confidence=0.8,
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": "Madrid."}}]}
    )


def test_handler_speaks_openai_chat_api():
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok(request)

    handler = LocalModelHandler("http://localhost:11434", model="llama3.2",
                                transport=httpx.MockTransport(responder))
    result = handler.run(_intent("hi"))
    handler.close()

    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["body"]["model"] == "llama3.2"
    assert seen["body"]["messages"][0]["content"] == "hi"
    assert result.output == "Madrid."
    assert result.metadata["cost"] == 0.0


def test_local_answer_is_real_not_a_stub():
    # The whole point: a local-model answer is scored as a real answer, unlike
    # the "[local] ..." heuristic placeholder.
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [
            {"message": {"content": "La capitale de l'Espagne est Madrid."}}
        ]})

    handler = LocalModelHandler("http://x", transport=httpx.MockTransport(responder))
    result = handler.run(_intent())
    handler.close()
    assert assess_quality(result.output, result.success, result.metadata).score >= 0.8


def test_handler_fails_open_when_model_unreachable():
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    handler = LocalModelHandler("http://x", transport=httpx.MockTransport(responder))
    result = handler.run(_intent())
    handler.close()
    assert result.success is False
    assert "[local-unavailable]" in result.output
    # Degraded local output is scored low — never mistaken for a good answer.
    assert assess_quality(result.output, result.success, result.metadata).score <= 0.3


def test_build_returns_none_without_config(monkeypatch):
    monkeypatch.delenv("AXIOMN_LOCAL_URL", raising=False)
    assert build_local_handler() is None


def test_build_reads_env(monkeypatch):
    monkeypatch.setenv("AXIOMN_LOCAL_URL", "http://localhost:11434")
    monkeypatch.setenv("AXIOMN_LOCAL_MODEL", "mistral")
    handler = build_local_handler()
    assert isinstance(handler, LocalModelHandler)
    assert handler.model == "mistral"
    handler.close()


def test_registry_uses_local_model_when_configured():
    handler = LocalModelHandler("http://x", transport=httpx.MockTransport(_ok))
    registry = default_registry(local_handler=handler)
    tool = registry.best_for(Route.LOCAL_AI, _intent())
    assert tool.name == "local_model"
    handler.close()


def test_registry_falls_back_to_heuristic_stub_by_default():
    registry = default_registry()
    assert registry.best_for(Route.LOCAL_AI, _intent()).name == "local_heuristic"
