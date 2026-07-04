"""The intelligence budget — the first rule of the constitution.

The owner sets a spend cap per client per window; inside it, AXIOMN is free to
route as it sees fit, but it may never exceed it. When a request would push a
client over budget, the guard doesn't fail it — it **routes down to the free
local tier** and says so. That is the "manage intelligence like a portfolio"
idea made concrete: spend on what matters, economize when the budget is tight,
never surprise the owner with a bill.

Backed by the shared `Store`, so the cap holds across every instance (see
`store.py`). Disabled by default (`AXIOMN_BUDGET_PER_MINUTE=0`): no cap, no
behavior change.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from .router.router import Route
from .store import Store


@dataclass
class BudgetDecision:
    route: Route  # the route to actually run (possibly downgraded)
    downgraded: bool
    note: Optional[str]
    enabled: bool
    limit: float
    spent: float

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "limit": round(self.limit, 6),
            "spent": round(self.spent, 6),
            "remaining": round(max(0.0, self.limit - self.spent), 6) if self.enabled else None,
            "downgraded": self.downgraded,
            "note": self.note,
        }


class BudgetGuard:
    """Enforces a per-client spend cap by routing down when it would be exceeded."""

    def __init__(self, store: Store, limit_per_window: float = 0.0, window_seconds: float = 60.0):
        self.store = store
        self.limit = limit_per_window
        self.window_seconds = window_seconds

    @property
    def enabled(self) -> bool:
        return self.limit > 0

    def _key(self, client_id: str) -> str:
        bucket = int(time.time() // self.window_seconds)
        return f"budget:{client_id}:{bucket}"

    def spent(self, client_id: str) -> float:
        return self.store.get(self._key(client_id))

    def enforce(
        self, client_id: str, route: Route, cost_of: Callable[[Route], float]
    ) -> BudgetDecision:
        """Decide the route to run given the client's remaining budget.

        `cost_of` estimates a route's cost (route-level; the real spend is
        recorded after execution). If the chosen route fits, it's kept; if not,
        and it isn't already the free local tier, it's downgraded to LOCAL_AI.
        """
        spent = self.spent(client_id)
        if not self.enabled:
            return BudgetDecision(route, False, None, False, 0.0, spent)
        if route == Route.LOCAL_AI or spent + cost_of(route) <= self.limit:
            return BudgetDecision(route, False, None, True, self.limit, spent)
        note = (
            f"Budget nearly spent ({round(spent, 4)}/{self.limit}); routed to the free "
            "local tier instead of a paid model to stay within your cap."
        )
        return BudgetDecision(Route.LOCAL_AI, True, note, True, self.limit, spent)

    def record(self, client_id: str, cost: float) -> None:
        """Record actual spend after execution (no-op when disabled or free)."""
        if self.enabled and cost > 0:
            self.store.incr(self._key(client_id), cost, ttl_seconds=self.window_seconds)


def build_budget_guard(store: Store) -> BudgetGuard:
    """Build the guard from `AXIOMN_BUDGET_PER_MINUTE` (cost units; 0 = off)."""
    import os

    try:
        limit = float(os.environ.get("AXIOMN_BUDGET_PER_MINUTE", "0"))
    except ValueError:
        limit = 0.0
    return BudgetGuard(store, limit_per_window=limit)
