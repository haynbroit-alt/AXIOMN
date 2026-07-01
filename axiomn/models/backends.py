"""Backends resolve an Intent once the Router has picked a Route.

Each backend implements the same `run(intent) -> str` contract, so a real
LLM client (Claude, a local Ollama model, ...) or a human-in-the-loop queue
can be swapped in without touching the Router or the API layer.
"""
from typing import Protocol

from ..intent.schema import Intent


class Backend(Protocol):
    def run(self, intent: Intent) -> str: ...


class LocalHeuristicBackend:
    """Instant, on-device resolution for low-difficulty intents."""

    def run(self, intent: Intent) -> str:
        return f"[local] {intent.category.value} answer for: {intent.topic}"


class CloudBackendStub:
    """Placeholder for a real cloud LLM call. Wire an actual client's
    `.run()` in here (e.g. an Anthropic Messages API call) to replace it."""

    def run(self, intent: Intent) -> str:
        return f"[cloud-stub] deeper reasoning requested for: {intent.text}"


class HumanQueueBackend:
    """Placeholder for routing to a human/expert network (e.g. StudyMesh)."""

    def run(self, intent: Intent) -> str:
        return f"Queued for a human/expert: {intent.topic}"
