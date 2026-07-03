"""Pluggable category classifiers for the Intent Engine.

`IntentEngine` only needs a `classify(text) -> Classification` callable —
the same "narrow contract" pattern already used for `Backend` in the
execution layer. `HeuristicIntentClassifier` (default) is keyword-driven,
offline, and fast. `SemanticIntentClassifier` (see `embedding.py`) is a
drop-in upgrade that matches by meaning instead of by shared words. Both
report `ambiguity`: how close the runner-up category came to winning, on
top of `confidence` (how strong the winning signal itself was) — a
request can be simultaneously confident and ambiguous (a clear, but
tied, match) or unsure but unambiguous (a weak match with nothing else
close behind it). The Router uses `ambiguity` to prefer escalating to a
human when the category itself is a toss-up, independent of difficulty.
"""
from dataclasses import dataclass
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


@dataclass
class Classification:
    category: IntentCategory
    confidence: float  # 0.0 .. 1.0 — how strong the winning signal was
    ambiguity: float = 0.0  # 0.0 .. 1.0 — how close the runner-up came to winning


class IntentClassifier(Protocol):
    def classify(self, normalized_text: str) -> Classification: ...


class HeuristicIntentClassifier:
    """Keyword-overlap classifier. No network, no model, fully deterministic."""

    def classify(self, normalized_text: str) -> Classification:
        scores = {
            category: sum(1 for keyword in keywords if keyword in normalized_text)
            for category, keywords in _KEYWORDS.items()
        }
        ranked = sorted(scores.values(), reverse=True)
        best_score, runner_up_score = ranked[0], ranked[1]

        if best_score == 0:
            return Classification(category=IntentCategory.UNKNOWN, confidence=0.2, ambiguity=1.0)

        best_category = max(scores, key=lambda c: scores[c])
        confidence = round(min(1.0, 0.4 + 0.2 * best_score), 2)
        ambiguity = round(runner_up_score / best_score, 2)
        return Classification(category=best_category, confidence=confidence, ambiguity=ambiguity)
