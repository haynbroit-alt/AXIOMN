from axiomn.intent.engine import IntentEngine
from axiomn.intent.schema import IntentCategory


def test_classifies_learn_intent():
    intent = IntentEngine().classify("Explain how neural networks work")
    assert intent.category == IntentCategory.LEARN
    assert intent.language == "en"


def test_classifies_solve_intent_in_french():
    intent = IntentEngine().classify("Aide-moi à résoudre ce bug dans mon code")
    assert intent.category == IntentCategory.SOLVE


def test_classifies_connect_intent():
    intent = IntentEngine().classify("Trouve un expert en droit fiscal pour moi")
    assert intent.category == IntentCategory.CONNECT


def test_difficulty_scales_with_complexity_markers():
    simple = IntentEngine().classify("Hi")
    complex_ = IntentEngine().classify(
        "Design a distributed system architecture and optimize it, then prove correctness"
    )
    assert complex_.difficulty > simple.difficulty


def test_unknown_intent_has_low_confidence():
    intent = IntentEngine().classify("asdkj qweqw zxczxc")
    assert intent.category == IntentCategory.UNKNOWN
    assert intent.confidence < 0.5
