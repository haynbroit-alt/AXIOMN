"""The Router: a cost/latency/trust-aware policy engine, not a fixed threshold.

Each route is described by a `RouteProfile`: how hard a request it can
reliably handle (`capability`), what it costs, how long it takes, and a
`trust_score` that is updated from real outcomes via `record_outcome`. This
is a transparent, auditable scoring function — the same shape a
reinforcement-learned policy would eventually fit into — rather than a
black box, which keeps it debuggable while still being genuinely dynamic:
repeated failures on a route lower its score until the router stops
choosing it.
"""
from dataclasses import dataclass, field
from enum import Enum

from ..intent.schema import Intent, IntentCategory


class Route(str, Enum):
    LOCAL_AI = "local_ai"
    CLOUD_AI = "cloud_ai"
    HUMAN_QUEUE = "human_queue"


@dataclass
class RouteProfile:
    route: Route
    capability: int  # highest intent difficulty (1-10) this route reliably handles
    cost_per_call: float  # relative cost unit; higher = more expensive
    latency_ms: float  # expected latency
    trust_score: float = 0.8  # 0..1, updated over time by record_outcome
    affinity: dict[IntentCategory, float] = field(default_factory=dict)


def _default_profiles() -> list[RouteProfile]:
    return [
        RouteProfile(route=Route.LOCAL_AI, capability=4, cost_per_call=0.0, latency_ms=50, trust_score=0.85),
        RouteProfile(route=Route.CLOUD_AI, capability=8, cost_per_call=0.02, latency_ms=800, trust_score=0.9),
        RouteProfile(
            route=Route.HUMAN_QUEUE,
            capability=10,
            cost_per_call=0.5,
            latency_ms=600_000,
            trust_score=0.97,
            affinity={IntentCategory.CONNECT: 5.0},
        ),
    ]


class Router:
    def __init__(
        self,
        profiles: list[RouteProfile] | None = None,
        cost_weight: float = 1.0,
        latency_weight: float = 0.3,
    ):
        self.profiles = profiles or _default_profiles()
        self.cost_weight = cost_weight
        self.latency_weight = latency_weight

    def route(self, intent: Intent) -> Route:
        feasible = [p for p in self.profiles if p.capability >= intent.difficulty]
        candidates = feasible or self.profiles  # best effort if nothing fully qualifies
        max_cost = max((p.cost_per_call for p in candidates), default=0.0) or 1.0
        max_latency = max((p.latency_ms for p in candidates), default=0.0) or 1.0
        best = max(candidates, key=lambda p: self._score(p, intent, max_cost, max_latency))
        return best.route

    def _score(self, profile: RouteProfile, intent: Intent, max_cost: float, max_latency: float) -> float:
        affinity_bonus = profile.affinity.get(intent.category, 0.0)
        cost_norm = profile.cost_per_call / max_cost
        latency_norm = profile.latency_ms / max_latency
        return (
            profile.trust_score * intent.confidence
            + affinity_bonus
            - self.cost_weight * cost_norm
            - self.latency_weight * latency_norm
        )

    def record_outcome(self, route: Route, success: bool, decay: float = 0.1) -> None:
        """Update a route's trust score from a real execution outcome (EMA)."""
        for profile in self.profiles:
            if profile.route == route:
                target = 1.0 if success else 0.0
                profile.trust_score = (1 - decay) * profile.trust_score + decay * target
                return
