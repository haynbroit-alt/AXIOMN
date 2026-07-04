"""The Execution Layer: picks a tool for the Router's chosen Route, runs it,
times it, and measures the quality of what came back.

Quality is *always* measured (it flows to metrics, the response, and the audit
trail). Whether that quality also mutates the Router's trust scores *live* is
opt-in (`adapt_routing`), off by default. That default is deliberate: online
self-modification makes routing non-deterministic — two identical requests can
route differently as trust drifts mid-stream — which is exactly the instability
that kills trust in a router. So by default AXIOMN records quality for
offline/batch tuning and keeps decisions stable; turning `adapt_routing` on
closes the loop live, letting a route that returns stubs lose trust over time.
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
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        router: Router | None = None,
        adapt_routing: bool = False,
    ):
        self.registry = registry or default_registry()
        self.router = router
        self.adapt_routing = adapt_routing

    def execute(self, route: Route, intent: Intent) -> ExecutionOutcome:
        tool = self.registry.best_for(route, intent)
        start = time.perf_counter()
        result = tool.handler.run(intent)
        latency_ms = (time.perf_counter() - start) * 1000
        quality = assess_quality(result.output, result.success, result.metadata)
        if self.router is not None and self.adapt_routing:
            # Live loop (opt-in): feed measured quality into trust, not a bare
            # bool — a route that "succeeds" with a placeholder answer still
            # loses trust. Off by default so routing stays deterministic.
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
