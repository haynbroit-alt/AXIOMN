from axiomn.gateway.catalog import default_catalog
from axiomn.gateway.providers import SimulatedClient
from axiomn.intent.classifiers import HeuristicIntentClassifier
from axiomn.intent.engine import IntentEngine
from axiomn.intent.llm_fallback import (
    LLMFallbackClassifier,
    build_default_fallback_classifier,
)
from axiomn.intent.schema import IntentCategory


class RecordingClient:
    def __init__(self, answer: str):
        self.answer = answer
        self.calls: list[str] = []

    def complete(self, model, intent):
        self.calls.append(intent.text)
        return self.answer


def test_crisp_requests_never_pay_for_an_llm_call():
    client = RecordingClient("learn")
    classifier = LLMFallbackClassifier(client=client, model_id="claude-haiku-4-5")

    result = classifier.classify("explain how black holes form")

    assert result.category is IntentCategory.LEARN  # heuristic's own answer
    assert client.calls == []  # the fallback was not consulted


def test_unknown_requests_are_classified_by_meaning():
    # The production black hole: no keyword matches, heuristic says UNKNOWN
    # with ambiguity 1.0, and the request used to dead-end in an unstaffed
    # human queue. The LLM second opinion routes it like a normal request.
    client = RecordingClient("learn")
    classifier = LLMFallbackClassifier(client=client, model_id="claude-haiku-4-5")

    result = classifier.classify("dit moi tous sur toi")

    assert result.category is IntentCategory.LEARN
    assert result.confidence == 0.7
    assert result.ambiguity == 0.2  # low enough not to trigger human escalation
    assert len(client.calls) == 1
    assert "dit moi tous sur toi" in client.calls[0]


def test_unparseable_answer_falls_back_to_the_heuristic_result():
    client = RecordingClient("I could not decide, sorry!")
    classifier = LLMFallbackClassifier(client=client, model_id="m")

    result = classifier.classify("dit moi tous sur toi")

    assert result.category is IntentCategory.UNKNOWN  # heuristic's honest answer
    assert result.ambiguity == 1.0


def test_provider_failure_never_breaks_classification():
    class ExplodingClient:
        def complete(self, model, intent):
            raise ConnectionError("provider down")

    classifier = LLMFallbackClassifier(client=ExplodingClient(), model_id="m")
    result = classifier.classify("dit moi tous sur toi")

    assert result.category is IntentCategory.UNKNOWN  # fail open, no exception


def test_simulated_client_cannot_masquerade_as_a_classification():
    # SimulatedClient echoes "[simulated:...] unknown answer for: ..." —
    # 'unknown' is not a classifiable category, so keyless deployments
    # keep the heuristic's behavior exactly.
    classifier = LLMFallbackClassifier(client=SimulatedClient(), model_id="claude-haiku-4-5")
    result = classifier.classify("dit moi tous sur toi")

    assert result.category is IntentCategory.UNKNOWN
    assert result.ambiguity == 1.0


def test_word_boundary_parsing_ignores_partial_matches():
    client = RecordingClient("this is unconnected to solvents")  # no whole category word
    classifier = LLMFallbackClassifier(client=client, model_id="m")
    assert classifier.classify("dit moi tous sur toi").category is IntentCategory.UNKNOWN


def test_end_to_end_through_the_intent_engine():
    engine = IntentEngine(
        classifier=LLMFallbackClassifier(client=RecordingClient("connect"), model_id="m")
    )
    intent = engine.classify("Quelqu'un pour m'aider demain matin ?")
    assert intent.category is IntentCategory.CONNECT


def test_builder_picks_the_cheapest_catalog_model():
    catalog = default_catalog()
    clients = {"anthropic": SimulatedClient(), "openai": SimulatedClient()}
    classifier = build_default_fallback_classifier(catalog, clients)

    cheapest = min(catalog.profiles, key=lambda p: p.cost_per_call)
    assert classifier.model_id == cheapest.model_id == "claude-haiku-4-5"
    assert isinstance(classifier.primary, HeuristicIntentClassifier)
