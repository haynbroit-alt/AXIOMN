"""Pluggable category classifiers for the Intent Engine.

`IntentEngine` only needs a `classify(text) -> (category, confidence)`
callable — this is the same "narrow contract" pattern already used for
`Backend` in the execution layer. `HeuristicIntentClassifier` (default) is
keyword-driven, offline, and fast. `SemanticIntentClassifier` (see
`embedding.py`) is a drop-in upgrade that matches by meaning instead of by
shared words.
"""
from typing import Protocol

from .schema import IntentCategory

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


class IntentClassifier(Protocol):
    def classify(self, normalized_text: str) -> tuple[IntentCategory, float]: ...


class HeuristicIntentClassifier:
    """Keyword-overlap classifier. No network, no model, fully deterministic."""

    def classify(self, normalized_text: str) -> tuple[IntentCategory, float]:
        best_category = IntentCategory.UNKNOWN
        best_score = 0
        for category, keywords in _KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in normalized_text)
            if score > best_score:
                best_score = score
                best_category = category
        confidence = min(1.0, 0.4 + 0.2 * best_score) if best_score else 0.2
        return best_category, round(confidence, 2)
