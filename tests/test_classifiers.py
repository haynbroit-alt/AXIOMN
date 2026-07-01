from axiomn.intent.classifiers import HeuristicIntentClassifier
from axiomn.intent.schema import IntentCategory


def test_classifies_create_intent():
    category, confidence = HeuristicIntentClassifier().classify("crée un plan de projet pour moi")
    assert category == IntentCategory.CREATE
    assert confidence > 0.5


def test_classifies_automate_intent():
    category, _ = HeuristicIntentClassifier().classify("automatise l'envoi de ce rapport chaque lundi")
    assert category == IntentCategory.AUTOMATE


def test_no_keyword_match_is_unknown_with_low_confidence():
    category, confidence = HeuristicIntentClassifier().classify("zzz qux flerbnorp")
    assert category == IntentCategory.UNKNOWN
    assert confidence == 0.2
