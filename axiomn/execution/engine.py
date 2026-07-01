"""The Execution Layer: picks a tool for the Router's chosen Route, runs it,
times it, and — if wired to a `Router` — reports success/failure back so
future routing decisions are grounded in what actually happened, closing
the loop between execution and the Router's trust scores.
"""
import time
from dataclasses import dataclass

from ..intent.schema import Intent
from ..models.tools import ToolRegistry, default_registry
from ..router.router import Route, Router


@dataclass
class ExecutionOutcome:
    output: str
    tool_name: str
    success: bool
    latency_ms: float


class ExecutionEngine:
    def __init__(self, registry: ToolRegistry | None = None, router: Router | None = None):
        self.registry = registry or default_registry()
        self.router = router

    def execute(self, route: Route, intent: Intent) -> ExecutionOutcome:
        tool = self.registry.best_for(route, intent)
        start = time.perf_counter()
        result = tool.handler.run(intent)
        latency_ms = (time.perf_counter() - start) * 1000
        if self.router is not None:
            self.router.record_outcome(route, success=result.success)
        return ExecutionOutcome(
            output=result.output,
            tool_name=tool.name,
            success=result.success,
            latency_ms=latency_ms,
        )
