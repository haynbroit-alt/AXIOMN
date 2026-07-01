"""Tool Registry: generalizes a fixed one-backend-per-route switch into a set
of named, tagged tools. The Execution Layer picks the best-fitting tool for
whatever Route the Router chose, instead of assuming there is exactly one
way to resolve each route. Each tool reports whether it actually succeeded,
which is what lets the Execution Layer close the loop back to the Router
(see `ExecutionEngine`).
"""
from dataclasses import dataclass, field
from typing import Protocol

from ..intent.schema import Intent, IntentCategory
from ..router.router import Route


@dataclass
class ToolResult:
    output: str
    success: bool = True


class ToolHandler(Protocol):
    def run(self, intent: Intent) -> ToolResult: ...


@dataclass
class Tool:
    name: str
    route: Route
    handler: ToolHandler
    affinity: set[IntentCategory] = field(default_factory=set)


class ToolRegistry:
    def __init__(self):
        self._tools: list[Tool] = []

    def register(self, tool: Tool) -> None:
        self._tools.append(tool)

    def best_for(self, route: Route, intent: Intent) -> Tool:
        candidates = [t for t in self._tools if t.route == route]
        if not candidates:
            raise LookupError(f"No tool registered for route {route!r}")
        specialists = [t for t in candidates if intent.category in t.affinity]
        return specialists[0] if specialists else candidates[0]


class LocalHeuristicHandler:
    """Instant, on-device resolution for low-difficulty intents."""

    def run(self, intent: Intent) -> ToolResult:
        return ToolResult(output=f"[local] {intent.category.value} answer for: {intent.topic}")


class CloudHandlerStub:
    """Placeholder for a real cloud LLM call. Wire an actual client's
    `.run()` in here (e.g. an Anthropic Messages API call) to replace it."""

    def run(self, intent: Intent) -> ToolResult:
        return ToolResult(output=f"[cloud-stub] deeper reasoning requested for: {intent.text}")


class HumanQueueHandler:
    """Placeholder for routing to a human/expert network (e.g. StudyMesh)."""

    def run(self, intent: Intent) -> ToolResult:
        return ToolResult(output=f"Queued for a human/expert: {intent.topic}")


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool(name="local_heuristic", route=Route.LOCAL_AI, handler=LocalHeuristicHandler()))
    registry.register(Tool(name="cloud_llm_stub", route=Route.CLOUD_AI, handler=CloudHandlerStub()))
    registry.register(
        Tool(
            name="human_expert_queue",
            route=Route.HUMAN_QUEUE,
            handler=HumanQueueHandler(),
            affinity={IntentCategory.CONNECT},
        )
    )
    return registry
