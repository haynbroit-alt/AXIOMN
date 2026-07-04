from axiomn.intent.classifiers import Classification
from axiomn.intent.engine import IntentEngine
from axiomn.intent.schema import IntentCategory
from axiomn.router.router import Route, Router


def test_short_high_stakes_request_routes_up_end_to_end():
    """The field regression: 'construis-moi un projet argent' used to score
    difficulty 1/10 and go to the cheapest model. It should now earn a strong
    model on expected value, while a trivial lookup still stays local."""
    engine, router = IntentEngine(), Router()

    money = engine.classify("Construis-moi un business rentable basé sur l'IA")
    assert money.value >= 0.6
    assert router.route(money) == Route.CLOUD_AI

    trivial = engine.classify("Quelle est la capitale de l'Espagne ?")
    assert trivial.value <= 0.35
    assert router.route(trivial) == Route.LOCAL_AI


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


def test_engine_delegates_category_to_injected_classifier():
    class FakeClassifier:
        def classify(self, normalized_text):
            return Classification(category=IntentCategory.CREATE, confidence=0.99, ambiguity=0.3)

    intent = IntentEngine(classifier=FakeClassifier()).classify("anything at all")
    assert intent.category == IntentCategory.CREATE
    assert intent.confidence == 0.99
    assert intent.ambiguity == 0.3
