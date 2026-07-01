from axiomn.intent.schema import Intent, IntentCategory
from axiomn.router.router import Route, Router


def _intent(difficulty: int, category: IntentCategory = IntentCategory.LEARN) -> Intent:
    return Intent(text="x", category=category, topic="x", language="en", difficulty=difficulty, confidence=0.5)


def test_low_difficulty_routes_to_local_ai():
    assert Router().route(_intent(2)) == Route.LOCAL_AI


def test_medium_difficulty_routes_to_cloud_ai():
    assert Router().route(_intent(5)) == Route.CLOUD_AI


def test_high_difficulty_routes_to_human_queue():
    assert Router().route(_intent(9)) == Route.HUMAN_QUEUE


def test_connect_intent_always_routes_to_human_queue():
    assert Router().route(_intent(1, category=IntentCategory.CONNECT)) == Route.HUMAN_QUEUE
