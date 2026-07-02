"""Provider adapters exercised against a mock HTTP transport: the exact
request shape each vendor expects (URL, auth header, payload) and the exact
response shape each returns. This is what 'switch providers without
rewriting your application' rests on, so it's pinned by tests — a real-call
verification additionally needs an API key (see ROADMAP, Capabilities)."""
import json

import httpx
import pytest

from axiomn.gateway.providers import AnthropicClient, OpenAIClient
from axiomn.intent.schema import Intent, IntentCategory


def _intent(text: str = "Explain black holes") -> Intent:
    return Intent(
        text=text,
        category=IntentCategory.LEARN,
        topic=text,
        language="en",
        difficulty=5,
        confidence=0.8,
    )


def test_anthropic_client_speaks_the_messages_api():
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers.get("x-api-key")
        seen["version"] = request.headers.get("anthropic-version")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": "Black holes form when..."}]}
        )

    client = AnthropicClient(api_key="sk-test", transport=httpx.MockTransport(responder))
    answer = client.complete("claude-haiku", _intent())
    client.close()

    assert answer == "Black holes form when..."
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["api_key"] == "sk-test"
    assert seen["version"] == "2023-06-01"
    assert seen["payload"]["model"] == "claude-haiku"
    assert seen["payload"]["messages"] == [{"role": "user", "content": "Explain black holes"}]
    assert seen["payload"]["max_tokens"] > 0


def test_openai_client_speaks_the_chat_completions_api():
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "An answer."}}]}
        )

    client = OpenAIClient(api_key="sk-test", transport=httpx.MockTransport(responder))
    answer = client.complete("gpt-4o", _intent())
    client.close()

    assert answer == "An answer."
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["payload"]["model"] == "gpt-4o"
    assert seen["payload"]["messages"] == [{"role": "user", "content": "Explain black holes"}]


@pytest.mark.parametrize(
    "make_client",
    [
        lambda t: AnthropicClient(api_key="sk-test", transport=t),
        lambda t: OpenAIClient(api_key="sk-test", transport=t),
    ],
    ids=["anthropic", "openai"],
)
def test_http_errors_raise_instead_of_returning_garbage(make_client):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(429, json={"error": "rate limited"})
    )
    client = make_client(transport)
    with pytest.raises(httpx.HTTPStatusError):
        client.complete("any-model", _intent())
    client.close()
