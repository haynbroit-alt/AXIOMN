"""LLM fallback classification: AXIOMN uses its own Gateway to understand.

The keyword heuristic is fast and free, but blind to anything phrased
without its keywords — production showed casual questions ("Dit moi tous
sur toi") classifying as UNKNOWN with ambiguity 1.0 and escalating to a
human queue that nobody staffs. The semantic embedding classifier fixes
that but needs a ~470MB model — too heavy for a small deployment VM.

This is the third way: keep the heuristic as the first pass, and only
when it fails (UNKNOWN, or the top categories are effectively tied) ask
the Gateway's cheapest model to classify by meaning. One short LLM call
at ~the catalog's lowest cost unit, only on the requests the heuristic
can't read. Fail-open by design: any provider error, timeout, or
unparseable answer returns the heuristic's own result — so offline,
keyless, and test environments behave exactly as before.
"""
import re

from ..gateway.catalog import ModelCatalog
from ..gateway.providers import ModelClient
from .classifiers import Classification, HeuristicIntentClassifier, IntentClassifier
from .schema import Intent, IntentCategory

_CLASSIFIABLE = [c for c in IntentCategory if c is not IntentCategory.UNKNOWN]

_PROMPT = (
    "Classify the user request below into exactly one category. Answer with "
    "one single word from this list and nothing else: "
    + ", ".join(c.value for c in _CLASSIFIABLE)
    + ".\n\nUser request: {text}"
)


def _parse_category(answer: str) -> IntentCategory | None:
    """The first classifiable category named in the answer, else None.
    Deliberately strict: an answer that names none (or is a simulated
    placeholder) must not be mistaken for a classification."""
    lowered = answer.lower()
    for category in _CLASSIFIABLE:
        if re.search(rf"\b{category.value}\b", lowered):
            return category
    return None


class LLMFallbackClassifier:
    """Heuristic-first classifier with a meaning-based LLM second opinion.

    Implements the same `IntentClassifier` contract, so it drops into
    `IntentEngine` without touching the Router or the Execution Layer.
    """

    def __init__(
        self,
        client: ModelClient,
        model_id: str,
        primary: IntentClassifier | None = None,
        ambiguity_threshold: float = 0.85,
    ):
        self.primary = primary or HeuristicIntentClassifier()
        self.client = client
        self.model_id = model_id
        self.ambiguity_threshold = ambiguity_threshold

    def classify(self, normalized_text: str) -> Classification:
        first_pass = self.primary.classify(normalized_text)
        heuristic_is_lost = (
            first_pass.category is IntentCategory.UNKNOWN
            or first_pass.ambiguity >= self.ambiguity_threshold
        )
        if not heuristic_is_lost:
            return first_pass

        prompt = _PROMPT.format(text=normalized_text)
        probe = Intent(
            text=prompt,
            category=IntentCategory.UNKNOWN,
            topic=normalized_text[:60],
            language="unknown",
            difficulty=1,
            confidence=0.0,
        )
        try:
            answer = self.client.complete(self.model_id, probe)
        except Exception:
            return first_pass  # fail open: provider trouble never breaks classification

        category = _parse_category(answer)
        if category is None:
            return first_pass
        # A meaning-based read from a real model: confident enough to route
        # normally, ambiguous enough to stay honest about being a fallback.
        return Classification(category=category, confidence=0.7, ambiguity=0.2)


def build_default_fallback_classifier(catalog: ModelCatalog, clients: dict[str, ModelClient]):
    """Wire the fallback to the catalog's cheapest model — classification
    should never cost flagship money."""
    cheapest = min(catalog.profiles, key=lambda p: p.cost_per_call)
    return LLMFallbackClassifier(client=clients[cheapest.provider], model_id=cheapest.model_id)
