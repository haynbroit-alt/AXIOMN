"""The Gateway's model catalog: which models exist, what each one costs,
how fast it is, and how hard a request it can reliably handle — and the
selection policy over them.

This is the product promise made executable: *"one API that automatically
picks the best model for every request, by cost, quality, and latency —
and shows you why."* The policy is deliberately simple and auditable:
among the models good enough for the request's difficulty, take the
cheapest (latency-adjusted); when nothing qualifies, take the most capable
one rather than fail. Every selection returns its reason as a string, so
the choice is explainable all the way to the client (the same
transparency-first rule the Router follows at the route level).

Costs are relative units set by the operator (real per-token billing
integration is roadmap work); the *savings* they let AXIOMN measure are
relative to `flagship()` — what every request would have cost if, like
most integrations, everything went to the premium model.
"""
from dataclasses import dataclass

from ..intent.schema import Intent


@dataclass
class ModelProfile:
    name: str  # e.g. "claude-haiku"
    provider: str  # e.g. "anthropic" — the key into the Gateway's client map
    quality: int  # 1-10, highest intent difficulty it reliably handles
    cost_per_call: float  # relative cost units, operator-configured
    latency_ms: float  # expected latency


class ModelCatalog:
    def __init__(self, profiles: list[ModelProfile], latency_weight: float = 0.1):
        if not profiles:
            raise ValueError("ModelCatalog needs at least one ModelProfile")
        self.profiles = profiles
        self.latency_weight = latency_weight

    def flagship(self) -> ModelProfile:
        """The premium model — the savings baseline: what a request would
        cost in the common no-routing setup where everything goes here."""
        return max(self.profiles, key=lambda p: (p.quality, p.cost_per_call))

    def select(self, intent: Intent) -> tuple[ModelProfile, str]:
        adequate = [p for p in self.profiles if p.quality >= intent.difficulty]
        if not adequate:
            best = self.flagship()
            reason = (
                f"difficulty {intent.difficulty} exceeds every model; "
                f"best effort with the most capable ({best.name}, quality {best.quality})"
            )
            return best, reason

        max_cost = max(p.cost_per_call for p in adequate) or 1.0
        max_latency = max(p.latency_ms for p in adequate) or 1.0
        best = min(
            adequate,
            key=lambda p: (
                p.cost_per_call / max_cost + self.latency_weight * (p.latency_ms / max_latency),
                -p.quality,
                p.name,
            ),
        )
        reason = (
            f"cheapest adequate model: quality {best.quality} >= difficulty "
            f"{intent.difficulty}, at {best.cost_per_call} cost units vs "
            f"{self.flagship().cost_per_call} for the flagship"
        )
        return best, reason


def default_catalog() -> ModelCatalog:
    """Three tiers across two providers — provider-mixing is the point:
    switching vendors is a catalog edit, not an application rewrite."""
    return ModelCatalog(
        [
            ModelProfile(name="claude-haiku", provider="anthropic", quality=6, cost_per_call=0.01, latency_ms=400),
            ModelProfile(name="gpt-4o", provider="openai", quality=8, cost_per_call=0.08, latency_ms=900),
            ModelProfile(name="claude-opus", provider="anthropic", quality=9, cost_per_call=0.15, latency_ms=1200),
        ]
    )
