"""The negotiator's voice: explain_decision turns the router's numbers into a
client-facing arbitration (headline, why, confidence, doubt, tradeoff). Offline.
"""
from axiomn.decision import explain_decision
from axiomn.intent.schema import Intent, IntentCategory, IntentSignals
from axiomn.router.router import Route


def _intent(category, *, confidence=0.8, ambiguity=0.0, signals=None) -> Intent:
    return Intent(
        text="x", category=category, topic="x", language="fr",
        difficulty=1, confidence=confidence, ambiguity=ambiguity,
        signals=signals or IntentSignals(),
    )


def test_cloud_decision_defends_the_spend():
    intent = _intent(IntentCategory.CREATE, signals=IntentSignals(creativity=0.8, stakes=0.8))
    exp = explain_decision(
        intent, Route.CLOUD_AI, demand=8, cost=0.03, baseline_cost=0.15,
        model="gpt-4o", model_reason="best quality/cost fit",
    )
    assert "worth it" in exp["headline"].lower()
    assert "0.8" in exp["why"]  # cites the expected value
    assert "gpt-4o" in exp["why"]
    assert "80%" in exp["tradeoff"] or "%" in exp["tradeoff"]
    assert exp["doubt"] is None  # crisp reading


def test_local_decision_frames_the_saving():
    intent = _intent(IntentCategory.LEARN, signals=IntentSignals(knowledge=0.3))
    exp = explain_decision(intent, Route.LOCAL_AI, demand=1, cost=0.0, baseline_cost=0.15)
    assert "cheap" in exp["headline"].lower()
    assert "budget" in exp["why"].lower()


def test_human_decision_is_the_honest_no():
    intent = _intent(IntentCategory.CONNECT, confidence=0.3, ambiguity=0.9)
    exp = explain_decision(intent, Route.HUMAN_QUEUE, demand=10, cost=0.5, baseline_cost=0.5)
    assert "human" in exp["headline"].lower()
    assert exp["doubt"] is not None  # high ambiguity is surfaced, not hidden


def test_doubt_is_surfaced_only_when_ambiguous():
    crisp = explain_decision(
        _intent(IntentCategory.LEARN, ambiguity=0.1), Route.LOCAL_AI,
        demand=1, cost=0.0, baseline_cost=0.15,
    )
    assert crisp["doubt"] is None

    unsure = explain_decision(
        _intent(IntentCategory.LEARN, ambiguity=0.5), Route.LOCAL_AI,
        demand=1, cost=0.0, baseline_cost=0.15,
    )
    assert unsure["doubt"] is not None


def test_low_confidence_is_stated_plainly():
    exp = explain_decision(
        _intent(IntentCategory.SOLVE, confidence=0.3), Route.LOCAL_AI,
        demand=1, cost=0.0, baseline_cost=0.15,
    )
    assert "tentativ" in exp["confidence_note"].lower()
