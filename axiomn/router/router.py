"""The Router: a cost/latency/trust-aware policy engine, not a fixed threshold.

Each route is described by a `RouteProfile`: how hard a request it can
reliably handle (`capability`), what it costs, how long it takes, a
`trust_score` that is updated from real outcomes via `record_outcome`, and
an `ambiguity_weight` describing how well it copes when the category
itself is a toss-up (see `Intent.ambiguity`, computed in
`intent/classifiers.py`). This is a transparent, auditable scoring
function — the same shape a reinforcement-learned policy would eventually
fit into — rather than a black box, which keeps it debuggable while still
being genuinely dynamic: repeated failures on a route lower its score
until the router stops choosing it.
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

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
    ambiguity_weight: float = 0.0  # how much this route benefits from Intent.ambiguity


def _default_profiles() -> list[RouteProfile]:
    return [
        # A keyword/heuristic backend can't reason about a toss-up between
        # two categories, so ambiguity earns it nothing.
        RouteProfile(
            route=Route.LOCAL_AI, capability=4, cost_per_call=0.0, latency_ms=50, trust_score=0.85,
        ),
        # A larger model can weigh competing interpretations somewhat better
        # than a keyword match, but it's still guessing.
        RouteProfile(
            route=Route.CLOUD_AI, capability=8, cost_per_call=0.02, latency_ms=800, trust_score=0.9,
            ambiguity_weight=0.5,
        ),
        # A human can just ask a clarifying question — genuinely ambiguous
        # requests should lean here regardless of difficulty.
        RouteProfile(
            route=Route.HUMAN_QUEUE,
            capability=10,
            cost_per_call=0.5,
            latency_ms=600_000,
            trust_score=0.97,
            affinity={IntentCategory.CONNECT: 5.0},
            ambiguity_weight=5.0,
        ),
    ]


class Router:
    def __init__(
        self,
        profiles: list[RouteProfile] | None = None,
        cost_weight: float = 1.0,
        latency_weight: float = 0.3,
        persistence_path: str | None = None,
    ):
        self.profiles = profiles or _default_profiles()
        self.cost_weight = cost_weight
        self.latency_weight = latency_weight
        self.persistence_path = persistence_path
        if self.persistence_path:
            self._load_trust_scores()

    def route(self, intent: Intent) -> Route:
        feasible = [p for p in self.profiles if p.capability >= intent.difficulty]
        candidates = feasible or self.profiles  # best effort if nothing fully qualifies
        max_cost = max((p.cost_per_call for p in candidates), default=0.0) or 1.0
        max_latency = max((p.latency_ms for p in candidates), default=0.0) or 1.0
        best = max(candidates, key=lambda p: self._score(p, intent, max_cost, max_latency))
        return best.route

    def _score(self, profile: RouteProfile, intent: Intent, max_cost: float, max_latency: float) -> float:
        affinity_bonus = profile.affinity.get(intent.category, 0.0)
        ambiguity_bonus = profile.ambiguity_weight * intent.ambiguity
        cost_norm = profile.cost_per_call / max_cost
        latency_norm = profile.latency_ms / max_latency
        return (
            profile.trust_score * intent.confidence
            + affinity_bonus
            + ambiguity_bonus
            - self.cost_weight * cost_norm
            - self.latency_weight * latency_norm
        )

    def record_outcome(self, route: Route, success: bool, decay: float = 0.1) -> None:
        """Update a route's trust score from a real execution outcome (EMA)."""
        for profile in self.profiles:
            if profile.route == route:
                target = 1.0 if success else 0.0
                profile.trust_score = (1 - decay) * profile.trust_score + decay * target
                if self.persistence_path:
                    self._save_trust_scores()
                return

    def _load_trust_scores(self) -> None:
        path = Path(self.persistence_path)
        if not path.exists():
            return
        try:
            saved = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return  # corrupt/unreadable state must never block startup
        for profile in self.profiles:
            if profile.route.value in saved:
                profile.trust_score = saved[profile.route.value]

    def _save_trust_scores(self) -> None:
        data = {profile.route.value: profile.trust_score for profile in self.profiles}
        Path(self.persistence_path).write_text(json.dumps(data))
