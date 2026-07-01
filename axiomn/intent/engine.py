"""The Intent Engine: turns raw text into a structured, language-agnostic Intent.

Category classification is delegated to a pluggable `IntentClassifier`
(default: `HeuristicIntentClassifier`, keyword-driven, offline, fast). Swap
in `SemanticIntentClassifier` (see `embedding.py`) for meaning-based
classification without touching the Router or the Execution Layer — both
only ever see an `Intent`.
"""
from langdetect import LangDetectException, detect

from .classifiers import HeuristicIntentClassifier, IntentClassifier
from .schema import Intent

_COMPLEXITY_MARKERS = [
    "prove", "architecture", "optimize", "research", "distributed system",
    "démontre", "optimise", "recherche approfondie",
]

_STOPWORDS = {
    "the", "a", "an", "is", "how", "does", "do", "what", "me", "to", "this",
    "le", "la", "les", "de", "du", "des", "que", "qui", "comment", "un", "une",
}


class IntentEngine:
    def __init__(self, classifier: IntentClassifier | None = None):
        self._classifier = classifier or HeuristicIntentClassifier()

    def classify(self, text: str) -> Intent:
        normalized = text.strip().lower()
        category, confidence = self._classifier.classify(normalized)
        return Intent(
            text=text,
            category=category,
            topic=self._extract_topic(text),
            language=self._detect_language(text),
            difficulty=self._estimate_difficulty(normalized),
            confidence=confidence,
        )

    def _estimate_difficulty(self, normalized: str) -> int:
        word_count = len(normalized.split())
        marker_hits = sum(1 for marker in _COMPLEXITY_MARKERS if marker in normalized)
        score = 1 + min(word_count // 8, 5) + marker_hits * 2
        return max(1, min(10, score))

    def _detect_language(self, text: str) -> str:
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"

    def _extract_topic(self, text: str) -> str:
        words = [w.strip(".,!?;:\"'") for w in text.split()]
        keywords = [w for w in words if w.lower() not in _STOPWORDS and len(w) > 2]
        return " ".join(keywords[:6]) if keywords else text[:30]
