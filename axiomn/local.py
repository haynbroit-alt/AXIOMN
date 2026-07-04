"""The local tier, made real.

The cheap tier used to return a template (`LocalHeuristicHandler` → `[local]…`),
so routing to it saved money by not really answering. `LocalModelHandler` points
that tier at a real small model over an **OpenAI-compatible** chat endpoint —
which is exactly what Ollama, llama.cpp's server, vLLM, and LM Studio all expose.
The model runs wherever you host it (typically on your own machine), so the tier
is genuinely free per call and your data never leaves for the cloud — the first
rule of the "constitution".

Opt-in and fail-open, like the rest of AXIOMN's edges: with no `AXIOMN_LOCAL_URL`
the runtime keeps the labeled stub (which the quality proxy scores low, so it is
never counted as a real answer); with a URL set, an unreachable model degrades to
a clearly-labeled unavailable result rather than taking the request down.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from .intent.schema import Intent
from .models.tools import ToolResult

DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MODEL = "local"


class LocalModelHandler:
    """A `ToolHandler` that answers from a local, OpenAI-compatible model."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT_S,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"content-type": "application/json"},
        )

    def run(self, intent: Intent) -> ToolResult:
        try:
            response = self._client.post(
                "/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": intent.text}],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            # Fail-open: the tier is unavailable, but the runtime stays up. The
            # "[local" marker means the quality proxy scores this low, so a
            # degraded local tier never masquerades as a good answer.
            return ToolResult(
                output=f"[local-unavailable] could not reach local model: {exc}",
                success=False,
                metadata={"model": self.model, "local": True, "cost": 0.0},
            )
        return ToolResult(
            output=content,
            metadata={
                "model": self.model,
                "local": True,
                "cost": 0.0,  # a locally-hosted model is free per call
                "selection_reason": f"local model ({self.model}) — free tier",
            },
        )

    def close(self) -> None:
        self._client.close()


def build_local_handler(
    base_url: Optional[str] = None,
    *,
    transport: Optional[httpx.BaseTransport] = None,
) -> Optional[LocalModelHandler]:
    """Construct the local-model handler from config, or ``None`` when unset.

    Resolution: the explicit ``base_url`` argument, then ``AXIOMN_LOCAL_URL``.
    ``AXIOMN_LOCAL_MODEL`` names the model (default ``local``). Unset ->
    ``None`` -> the registry keeps the labeled heuristic stub.
    """
    url = base_url or os.environ.get("AXIOMN_LOCAL_URL")
    if not url:
        return None
    model = os.environ.get("AXIOMN_LOCAL_MODEL", DEFAULT_MODEL)
    return LocalModelHandler(url, model=model, transport=transport)
