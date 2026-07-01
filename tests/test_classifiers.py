from axiomn.intent.classifiers import HeuristicIntentClassifier
from axiomn.intent.schema import IntentCategory


def test_classifies_create_intent():
    classification = HeuristicIntentClassifier().classify("crée un plan de projet pour moi")
    assert classification.category == IntentCategory.CREATE
    assert classification.confidence > 0.5


def test_classifies_automate_intent():
    classification = HeuristicIntentClassifier().classify("automatise l'envoi de ce rapport chaque lundi")
    assert classification.category == IntentCategory.AUTOMATE


def test_no_keyword_match_is_unknown_with_low_confidence_and_max_ambiguity():
    classification = HeuristicIntentClassifier().classify("zzz qux flerbnorp")
    assert classification.category == IntentCategory.UNKNOWN
    assert classification.confidence == 0.2
    assert classification.ambiguity == 1.0


def test_single_matching_keyword_is_unambiguous():
    classification = HeuristicIntentClassifier().classify("explique-moi les intégrales")
    assert classification.category == IntentCategory.LEARN
    assert classification.ambiguity == 0.0


def test_tied_keyword_matches_are_maximally_ambiguous():
    # "fix" (solve) and "build" (create) each match exactly once — a genuine toss-up.
    classification = HeuristicIntentClassifier().classify("fix and build this")
    assert classification.ambiguity == 1.0
