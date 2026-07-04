"""The intelligence budget: a per-client spend cap that routes down to the free
tier rather than exceed it. The constitution's first rule, made testable.
"""
from axiomn.budget import BudgetGuard, build_budget_guard
from axiomn.router.router import Route
from axiomn.store import InMemoryStore

# Route-level cost estimate, mirroring the router's default profiles.
_COST = {Route.LOCAL_AI: 0.0, Route.CLOUD_AI: 0.02, Route.HUMAN_QUEUE: 0.5}


def _cost_of(route: Route) -> float:
    return _COST[route]


def test_disabled_budget_never_changes_the_route():
    guard = BudgetGuard(InMemoryStore(), limit_per_window=0.0)
    d = guard.enforce("c", Route.CLOUD_AI, _cost_of)
    assert d.route == Route.CLOUD_AI
    assert d.enabled is False and d.downgraded is False


def test_request_within_budget_keeps_its_route():
    guard = BudgetGuard(InMemoryStore(), limit_per_window=1.0)
    d = guard.enforce("c", Route.CLOUD_AI, _cost_of)
    assert d.route == Route.CLOUD_AI and d.downgraded is False


def test_request_over_budget_is_routed_down_to_free_local():
    store = InMemoryStore()
    guard = BudgetGuard(store, limit_per_window=0.05)
    # Spend up to the cap on paid routes.
    guard.record("c", 0.02)
    guard.record("c", 0.02)  # spent 0.04, cap 0.05
    d = guard.enforce("c", Route.CLOUD_AI, _cost_of)  # 0.04 + 0.02 > 0.05
    assert d.route == Route.LOCAL_AI
    assert d.downgraded is True
    assert "budget" in (d.note or "").lower()


def test_free_local_route_is_never_downgraded():
    store = InMemoryStore()
    guard = BudgetGuard(store, limit_per_window=0.01)
    guard.record("c", 0.5)  # way over
    d = guard.enforce("c", Route.LOCAL_AI, _cost_of)
    assert d.route == Route.LOCAL_AI and d.downgraded is False


def test_budget_is_per_client():
    store = InMemoryStore()
    guard = BudgetGuard(store, limit_per_window=0.03)
    guard.record("a", 0.03)  # client a is spent
    assert guard.enforce("a", Route.CLOUD_AI, _cost_of).downgraded is True
    assert guard.enforce("b", Route.CLOUD_AI, _cost_of).downgraded is False  # b is fresh


def test_as_dict_reports_remaining():
    guard = BudgetGuard(InMemoryStore(), limit_per_window=1.0)
    guard.record("c", 0.3)
    d = guard.enforce("c", Route.CLOUD_AI, _cost_of)
    payload = d.as_dict()
    assert payload["enabled"] is True
    assert payload["remaining"] == 0.7


def test_build_reads_env(monkeypatch):
    monkeypatch.setenv("AXIOMN_BUDGET_PER_MINUTE", "0.25")
    guard = build_budget_guard(InMemoryStore())
    assert guard.enabled and guard.limit == 0.25
