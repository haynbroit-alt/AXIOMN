from axiomn.intent.schema import Intent, IntentCategory
from axiomn.router.router import Route, RouteProfile, Router


def _intent(difficulty: int, category: IntentCategory = IntentCategory.LEARN, ambiguity: float = 0.0) -> Intent:
    return Intent(
        text="x", category=category, topic="x", language="en",
        difficulty=difficulty, confidence=0.5, ambiguity=ambiguity,
    )


def test_low_difficulty_routes_to_local_ai():
    assert Router().route(_intent(2)) == Route.LOCAL_AI


def test_medium_difficulty_routes_to_cloud_ai():
    assert Router().route(_intent(5)) == Route.CLOUD_AI


def test_high_difficulty_routes_to_human_queue():
    assert Router().route(_intent(9)) == Route.HUMAN_QUEUE


def test_connect_intent_always_routes_to_human_queue():
    assert Router().route(_intent(1, category=IntentCategory.CONNECT)) == Route.HUMAN_QUEUE


def test_no_feasible_route_falls_back_to_best_effort():
    # difficulty exceeds every profile's capability; router must still return a route
    assert Router().route(_intent(11)) in {Route.LOCAL_AI, Route.CLOUD_AI, Route.HUMAN_QUEUE}


def test_repeated_failures_shift_future_routing():
    router = Router()
    intent = _intent(2)  # normally routed to local_ai
    assert router.route(intent) == Route.LOCAL_AI

    router.record_outcome(Route.LOCAL_AI, success=False)

    assert router.route(intent) == Route.CLOUD_AI


def test_custom_profiles_can_be_injected():
    router = Router(profiles=[
        RouteProfile(route=Route.CLOUD_AI, capability=10, cost_per_call=0.0, latency_ms=1, trust_score=1.0),
    ])
    assert router.route(_intent(2)) == Route.CLOUD_AI


def test_high_ambiguity_escalates_a_cloud_bound_request_to_human():
    # Same difficulty as test_medium_difficulty_routes_to_cloud_ai, but this
    # time the classifier couldn't tell two categories apart — a human can
    # just ask, so escalation should win even though cloud_ai is cheaper
    # and faster.
    assert Router().route(_intent(5, ambiguity=0.9)) == Route.HUMAN_QUEUE


def test_low_ambiguity_does_not_change_medium_difficulty_routing():
    assert Router().route(_intent(5, ambiguity=0.1)) == Route.CLOUD_AI


def test_trust_scores_persist_across_router_instances(tmp_path):
    state_path = str(tmp_path / "router_state.json")

    router = Router(persistence_path=state_path)
    router.record_outcome(Route.LOCAL_AI, success=False)
    degraded_trust = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)

    reloaded = Router(persistence_path=state_path)
    reloaded_trust = next(p.trust_score for p in reloaded.profiles if p.route == Route.LOCAL_AI)

    assert reloaded_trust == degraded_trust


def test_corrupt_state_file_never_blocks_startup(tmp_path):
    state_path = tmp_path / "router_state.json"
    state_path.write_text("{not json")

    router = Router(persistence_path=str(state_path))  # must not raise
    assert router.profiles  # defaults intact


def test_without_persistence_path_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    router = Router()
    router.record_outcome(Route.LOCAL_AI, success=False)
    assert list(tmp_path.iterdir()) == []
