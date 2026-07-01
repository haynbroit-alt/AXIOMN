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
