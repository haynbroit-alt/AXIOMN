"""Decision signals: routing on the expected value of a good answer, not just
textual difficulty. These are offline (no classification, no langdetect) — they
exercise the analyzer, the value math, and the Router's `demand` blend directly.
"""
from axiomn.intent.schema import Intent, IntentCategory, IntentSignals
from axiomn.intent.signals import analyze_signals
from axiomn.router.router import Route, Router


def _intent(difficulty: int, signals: IntentSignals, category=IntentCategory.CREATE) -> Intent:
    return Intent(
        text="x", category=category, topic="x", language="fr",
        difficulty=difficulty, confidence=0.8, signals=signals,
    )


def test_high_stakes_creative_request_scores_high_value():
    # "construis-moi un business rentable basé sur l'IA"
    sig = analyze_signals("construis-moi un business rentable basé sur l'ia", IntentCategory.CREATE)
    assert sig.creativity >= 0.5
    assert sig.stakes >= 0.3
    assert sig.value >= 0.6  # deserves a strong model


def test_trivial_factual_request_scores_low_value():
    sig = analyze_signals("quelle est la capitale de l'espagne", IntentCategory.LEARN)
    assert sig.value <= 0.35  # cheap model is fine


def test_value_weights_intelligence_need_and_stakes():
    sig = IntentSignals(reasoning=0.0, creativity=0.8, knowledge=0.0, stakes=0.8)
    # 0.55 * max(0,0.8,0) + 0.45 * 0.8 = 0.44 + 0.36 = 0.80
    assert sig.value == 0.8


def test_zero_signals_mean_value_zero():
    assert IntentSignals().value == 0.0


def test_demand_is_difficulty_when_value_is_zero():
    # Backward compatibility: no signals -> route on difficulty exactly as before.
    router = Router()
    assert router.demand(_intent(3, IntentSignals())) == 3


def test_demand_lifts_a_low_difficulty_high_value_request():
    # Difficulty 1 (short prompt) but high expected value -> demand jumps.
    high = IntentSignals(creativity=0.8, stakes=0.8)  # value 0.8 -> 8
    assert Router().demand(_intent(1, high)) == 8


def test_high_value_request_routes_up_not_to_the_cheapest_model():
    router = Router()
    high = IntentSignals(creativity=0.8, stakes=0.8)
    # The exact regression from the field: a short "build me a profitable
    # business" that used to score difficulty 1 and go local.
    assert router.route(_intent(1, high)) == Route.CLOUD_AI
    # A genuinely trivial request still stays on the cheap local route.
    assert router.route(_intent(1, IntentSignals())) == Route.LOCAL_AI
