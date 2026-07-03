"""Semantic (embedding-based) intent classification.

The heuristic classifier matches shared words. This module matches shared
*meaning*: text and a small set of canonical example utterances per category
are placed in the same vector space, and a request is assigned to whichever
category's examples are closest by cosine similarity. Because a multilingual
sentence embedding model places translations of the same sentence near each
other in that space, this works across languages without any translation
step — "explain how black holes form" and "explique comment se forment les
trous noirs" land in the same category on meaning alone.

This module has no hard dependency on any particular embedding provider:
`Embedder` is a one-method protocol, so a local sentence-transformers model,
a hosted embeddings API, or a test double can all be plugged in.
"""
import math
from typing import Protocol, Sequence

from .classifiers import Classification
from .schema import IntentCategory


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


_CANONICAL_EXAMPLES: dict[IntentCategory, list[str]] = {
    IntentCategory.LEARN: [
        "Explain how black holes form",
        "What is quantum entanglement",
        "Teach me the basics of calculus",
        "Comment fonctionne la photosynthèse",
        "Pourquoi le ciel est-il bleu",
    ],
    IntentCategory.SOLVE: [
        "Fix this bug in my code",
        "Why is my server crashing",
        "Aide-moi à résoudre cette erreur",
        "Debug this failing test",
        "Mon programme plante, aide-moi",
    ],
    IntentCategory.CREATE: [
        "Write a poem about the ocean",
        "Generate a logo for my startup",
        "Crée un plan de projet pour moi",
        "Build me a landing page",
        "Compose une chanson triste",
    ],
    IntentCategory.COMMUNICATE: [
        "Translate this paragraph to Spanish",
        "Summarize this article in three sentences",
        "Résume ce texte en trois phrases",
        "Rewrite this email to sound more formal",
        "Traduis ce message en anglais",
    ],
    IntentCategory.CONNECT: [
        "Find an expert in tax law near me",
        "Connect me with a mechanic",
        "Trouve un professeur de mathématiques",
        "I need to talk to a real person",
        "Mets-moi en relation avec un plombier",
    ],
    IntentCategory.AUTOMATE: [
        "Automate my morning report",
        "Schedule this task every Monday",
        "Automatise l'envoi de ce message chaque semaine",
        "Set up a recurring workflow",
        "Planifie cette tâche automatiquement",
    ],
}


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticIntentClassifier:
    """Classifies by nearest neighbor in embedding space, not keyword overlap."""

    def __init__(self, embedder: Embedder):
        self._embedder = embedder
        self._categories: list[IntentCategory] = []
        self._example_vectors: list[list[float]] = []
        for category, examples in _CANONICAL_EXAMPLES.items():
            for vector in embedder.encode(examples):
                self._categories.append(category)
                self._example_vectors.append(vector)

    def classify(self, normalized_text: str) -> Classification:
        [vector] = self._embedder.encode([normalized_text])

        best_per_category: dict[IntentCategory, float] = {}
        for category, example_vector in zip(self._categories, self._example_vectors):
            score = cosine_similarity(vector, example_vector)
            if score > best_per_category.get(category, -1.0):
                best_per_category[category] = score

        ranked = sorted(best_per_category.values(), reverse=True)
        top_sim, runner_up_sim = ranked[0], ranked[1]
        best_category = max(best_per_category, key=lambda c: best_per_category[c])

        confidence = round(max(0.0, min(1.0, (top_sim + 1) / 2)), 2)
        # A small gap between the best and second-best category means the
        # request could plausibly belong to either — that's ambiguity,
        # distinct from confidence (which only reflects the winner's
        # absolute similarity).
        ambiguity = round(max(0.0, min(1.0, 1.0 - (top_sim - runner_up_sim))), 2)
        return Classification(category=best_category, confidence=confidence, ambiguity=ambiguity)


class SentenceTransformerEmbedder:
    """Real embedding backend: a local multilingual sentence-transformers model.

    Lazily imports `sentence_transformers` so it stays an optional dependency —
    the default heuristic classifier never pays this cost.
    """

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return self._model.encode(list(texts)).tolist()
