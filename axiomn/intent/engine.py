"""The Intent Engine: turns raw text into a structured, language-agnostic Intent.

This is a deterministic, keyword-driven classifier by design. It has no
network dependency and no hidden model call, so it is cheap, fast, and
fully testable. Swap `IntentEngine` for an LLM-backed implementation later
(same `classify(text) -> Intent` contract) without touching the Router or
the Execution Layer.
"""
from langdetect import LangDetectException, detect

from .schema import Intent, IntentCategory

_KEYWORDS: dict[IntentCategory, list[str]] = {
    IntentCategory.LEARN: [
        "explain", "teach me", "what is", "how does", "how do",
        "explique", "apprends", "qu'est-ce que", "comment fonctionne",
    ],
    IntentCategory.SOLVE: [
        "fix", "debug", "error", "bug", "resolve", "help me solve",
        "résous", "erreur", "aide-moi à résoudre", "corrige",
    ],
    IntentCategory.CREATE: [
        "create", "build", "generate", "write", "design a",
        "crée", "génère", "écris", "construis",
    ],
    IntentCategory.COMMUNICATE: [
        "translate", "summarize", "rewrite", "draft a message",
        "traduis", "résume", "reformule",
    ],
    IntentCategory.CONNECT: [
        "find an expert", "connect me with", "talk to someone",
        "trouve un expert", "mets-moi en relation",
    ],
    IntentCategory.AUTOMATE: [
        "automate", "schedule", "run this every", "set up a workflow",
        "automatise", "planifie", "exécute automatiquement",
    ],
}

_COMPLEXITY_MARKERS = [
    "prove", "architecture", "optimize", "research", "distributed system",
    "démontre", "optimise", "recherche approfondie",
]

_STOPWORDS = {
    "the", "a", "an", "is", "how", "does", "do", "what", "me", "to", "this",
    "le", "la", "les", "de", "du", "des", "que", "qui", "comment", "un", "une",
}


class IntentEngine:
    def classify(self, text: str) -> Intent:
        normalized = text.strip().lower()
        category, confidence = self._match_category(normalized)
        return Intent(
            text=text,
            category=category,
            topic=self._extract_topic(text),
            language=self._detect_language(text),
            difficulty=self._estimate_difficulty(normalized),
            confidence=confidence,
        )

    def _match_category(self, normalized: str) -> tuple[IntentCategory, float]:
        best_category = IntentCategory.UNKNOWN
        best_score = 0
        for category, keywords in _KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in normalized)
            if score > best_score:
                best_score = score
                best_category = category
        confidence = min(1.0, 0.4 + 0.2 * best_score) if best_score else 0.2
        return best_category, round(confidence, 2)

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
