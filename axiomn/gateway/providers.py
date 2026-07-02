"""Provider adapters: the portability layer.

Every provider implements the same two-method contract (`complete`,
`close`), so switching from OpenAI to Anthropic to a local model is a
catalog edit, not an application rewrite — the application only ever
speaks to AXIOMN. Adapters are deliberately thin: one HTTP call, one
response-shape parse, no provider SDK dependency (just `httpx`, which the
server already uses).

`SimulatedClient` is the no-keys fallback so the Gateway is demonstrable
and testable offline; its output is explicitly labeled `[simulated:...]`
so a simulated answer can never pass for a real one.
"""
from typing import Optional, Protocol

import httpx

from ..intent.schema import Intent


class ModelClient(Protocol):
    def complete(self, model: str, intent: Intent) -> str: ...


class AnthropicClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        timeout: float = 30.0,
        max_tokens: int = 1024,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._max_tokens = max_tokens
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )

    def complete(self, model: str, intent: Intent) -> str:
        response = self._client.post(
            "/v1/messages",
            json={
                "model": model,
                "max_tokens": self._max_tokens,
                "messages": [{"role": "user", "content": intent.text}],
            },
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    def close(self) -> None:
        self._client.close()


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com",
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def complete(self, model: str, intent: Intent) -> str:
        response = self._client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": intent.text}],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def close(self) -> None:
        self._client.close()


class SimulatedClient:
    """Offline stand-in used when a provider has no API key configured.
    The `[simulated:...]` label is a hard honesty rule: a simulated answer
    must never be mistakable for a real model's."""

    def complete(self, model: str, intent: Intent) -> str:
        return f"[simulated:{model}] {intent.category.value} answer for: {intent.topic}"

    def close(self) -> None:
        pass
