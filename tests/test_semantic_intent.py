"""Unit tests for semantic classification mechanics, using a deterministic
hashing embedder instead of a real model — no network, no GPU, no
flakiness. These test the *nearest-neighbor logic*, not embedding quality;
`test_semantic_intent_live.py` covers the real model.
"""
from axiomn.intent.embedding import SemanticIntentClassifier, cosine_similarity
from axiomn.intent.schema import IntentCategory


class HashingEmbedder:
    """A toy bag-of-words embedder: good enough to make cosine similarity
    reflect word overlap, which is all the classifier logic needs to be
    exercised deterministically."""

    def __init__(self, dim: int = 64):
        self._dim = dim

    def encode(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * self._dim
            for word in text.lower().split():
                vector[hash(word) % self._dim] += 1.0
            vectors.append(vector)
        return vectors


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_classifies_by_nearest_example_not_exact_keyword():
    classifier = SemanticIntentClassifier(embedder=HashingEmbedder())
    category, confidence = classifier.classify("explain how black holes form in space")
    assert category == IntentCategory.LEARN
    assert 0.0 <= confidence <= 1.0


def test_classifies_solve_style_request():
    classifier = SemanticIntentClassifier(embedder=HashingEmbedder())
    category, _ = classifier.classify("debug this failing test for me")
    assert category == IntentCategory.SOLVE
