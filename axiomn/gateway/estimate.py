"""Savings estimation: the self-serve "bring your own traffic, see the receipts"
path — AXIOMN's sharpest standalone value proposition made measurable *before*
anyone integrates or spends a cent.

Given a batch of representative prompts, AXIOMN classifies and routes each one
(the same decision it would make live) and prices it against the no-routing
baseline where every request hits the flagship model. The result is a projected
bill, the baseline bill, and the difference — computed from *your* traffic, not
a marketing number.

This module is the pure arithmetic (fully offline, no model calls, no API keys),
so the numbers are trivially auditable and unit-tested. The endpoint that feeds
it real classifications lives in `axiomn/api/main.py`.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class EstimateRow:
    """One prompt's projected outcome: the route AXIOMN picked and its cost."""

    route: str
    cost: float
    baseline_cost: float


@dataclass
class SavingsEstimate:
    requests: int
    projected_cost: float
    baseline_cost: float
    saved: float
    savings_rate: float  # saved / baseline, 0.0 .. 1.0
    by_route: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "requests": self.requests,
            "projected_cost": round(self.projected_cost, 6),
            "baseline_cost": round(self.baseline_cost, 6),
            "saved": round(self.saved, 6),
            "savings_rate": round(self.savings_rate, 4),
            "by_route": self.by_route,
        }


def estimate_savings(rows: list[EstimateRow]) -> SavingsEstimate:
    """Aggregate per-request costs into a projected-vs-baseline savings report.

    `savings_rate` is the fraction of the baseline bill that routing avoids;
    it is 0.0 for an empty batch or when the baseline is zero, never negative
    or NaN (so callers can render it without guarding).
    """
    projected = sum(r.cost for r in rows)
    baseline = sum(r.baseline_cost for r in rows)
    saved = baseline - projected
    rate = saved / baseline if baseline > 0 else 0.0
    return SavingsEstimate(
        requests=len(rows),
        projected_cost=projected,
        baseline_cost=baseline,
        saved=saved,
        savings_rate=rate,
        by_route=dict(Counter(r.route for r in rows)),
    )
