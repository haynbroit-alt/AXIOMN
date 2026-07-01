"""Live integration test: a real multilingual sentence-transformers model.

Downloads a model on first run, so this is opt-in and excluded from the
default `pytest` run. Enable with:

    AXIOMN_LIVE_TESTS=1 pytest tests/test_semantic_intent_live.py
"""
import os

import pytest

from axiomn.intent.embedding import SemanticIntentClassifier, SentenceTransformerEmbedder
from axiomn.intent.schema import IntentCategory

pytestmark = pytest.mark.skipif(
    os.environ.get("AXIOMN_LIVE_TESTS") != "1",
    reason="opt-in: requires network access and a ~470MB model download",
)


def test_cross_lingual_requests_land_in_the_same_category():
    classifier = SemanticIntentClassifier(embedder=SentenceTransformerEmbedder())

    english, _ = classifier.classify("explain how black holes form")
    french, _ = classifier.classify("explique comment se forment les trous noirs")
    japanese, _ = classifier.classify("ブラックホールがどのように形成されるか説明してください")

    assert english == IntentCategory.LEARN
    assert french == IntentCategory.LEARN
    assert japanese == IntentCategory.LEARN
