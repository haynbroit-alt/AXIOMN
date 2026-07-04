"""The Execution Layer: picks a tool for the Router's chosen Route, runs it,
times it, measures the quality of what came back, and — if wired to a `Router` —
reports that quality back so future routing decisions are grounded in what
actually happened, closing the loop between execution and the Router's trust
scores. The loop learns from *quality*, not just a success flag: a route that
returns a stub or an empty answer loses trust and gets chosen less.
"""
import time
from dataclasses import dataclass, field

from ..intent.schema import Intent
from ..models.tools import ToolRegistry, default_registry
from ..quality import assess_quality
from ..router.router import Route, Router


@dataclass
class ExecutionOutcome:
    output: str
    tool_name: str
    success: bool
    latency_ms: float
    metadata: dict = field(default_factory=dict)
    # 0..1 proxy for how good the answer actually was, and why (see quality.py).
    # This — not the bare success flag — is what the Router learns from.
    quality: float = 1.0
    quality_reason: str = ""


class ExecutionEngine:
    def __init__(self, registry: ToolRegistry | None = None, router: Router | None = None):
        self.registry = registry or default_registry()
        self.router = router

    def execute(self, route: Route, intent: Intent) -> ExecutionOutcome:
        tool = self.registry.best_for(route, intent)
        start = time.perf_counter()
        result = tool.handler.run(intent)
        latency_ms = (time.perf_counter() - start) * 1000
        quality = assess_quality(result.output, result.success, result.metadata)
        if self.router is not None:
            # Feed the measured quality into the trust loop, not a bare bool:
            # a route that "succeeds" with a placeholder answer should still
            # lose trust over time.
            self.router.record_outcome(route, success=result.success, quality=quality.score)
        return ExecutionOutcome(
            output=result.output,
            tool_name=tool.name,
            success=result.success,
            latency_ms=latency_ms,
            metadata=result.metadata,
            quality=quality.score,
            quality_reason=quality.reason,
        )
