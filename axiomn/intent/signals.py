"""Decision signals: *how much intelligence a request deserves*, not just how
hard its words look.

The original router gated on a single `difficulty` scalar — roughly word count
plus a few complexity markers. That answers "is this hard to phrase?" but not
"does getting this right matter?", so a short, high-stakes request like
"construis-moi un business rentable" scored 1/10 and went to the cheapest model.

This module scores a request along several independent dimensions and combines
them into an **expected value** — the value of a *strong* answer weighed against
the cost of a weak one. The Router routes on that, not on difficulty alone
(`Router` blends the two into `demand`). The result is a router that says
"this question merits a lot of intelligence" rather than merely "this question
is hard".

All heuristic, offline, and deterministic — a transparent, tunable scoring
function (the same shape a learned policy would later fit into), not a black
box. Lexicons are bilingual (FR/EN) to match AXIOMN's user base.
"""
from __future__ import annotations

from .schema import IntentCategory, IntentSignals

# Each lexicon is a set of substrings; a hit nudges the corresponding dimension.
_CREATIVITY = {
    "build", "construis", "construire", "create", "crée", "créer", "conçois",
    "concevoir", "design", "write", "écris", "rédige", "rédiger", "invent",
    "invente", "generate", "génère", "imagine", "brainstorm", "story", "poème",
    "poem", "plan", "stratégie", "strategy", "startup", "business", "projet",
    "project", "app", "application", "site", "landing", "campagne", "campaign",
}
_REASONING = {
    "prove", "démontre", "optimize", "optimise", "analyze", "analyse", "analyser",
    "architecture", "algorithm", "algorithme", "debug", "refactor", "compare",
    "evaluate", "évalue", "why", "pourquoi", "explain", "explique", "reason",
    "raisonne", "distributed", "distribué", "scalable", "complex", "complexe",
    "trade-off", "tradeoff", "step by step", "étape par étape", "diagnose",
}
_KNOWLEDGE = {
    "research", "recherche", "comprehensive", "détaillé", "detailed", "in-depth",
    "approfondi", "history", "histoire", "science", "law", "droit", "medical",
    "médical", "technical", "technique", "documentation", "state of the art",
    "état de l'art", "literature", "littérature",
}
# Stakes: the consequence of a weak or wrong answer is high.
_STAKES = {
    "money", "argent", "rentable", "profit", "revenue", "revenu", "invest",
    "investissement", "financ", "budget", "legal", "juridique", "droit",
    "contract", "contrat", "medical", "médical", "santé", "health", "security",
    "sécurité", "production", "deploy", "déploie", "critical", "critique",
    "important", "safety", "sûreté", "tax", "impôt", "fiscal", "business",
    "startup", "client", "customer", "compliance", "conformité", "rgpd",
}


def _hits(text: str, lexicon: set[str]) -> int:
    return sum(1 for term in lexicon if term in text)


def _score(base: float, hits: int) -> float:
    # Base prior (from category) plus diminishing returns per keyword hit.
    return round(min(1.0, base + 0.3 * hits), 3)


def analyze_signals(normalized_text: str, category: IntentCategory) -> IntentSignals:
    """Score a normalized request across the decision dimensions.

    Category supplies a prior (a CREATE request is creative by default; a SOLVE
    request leans on reasoning), and keyword hits sharpen it.
    """
    creativity_base = 0.5 if category is IntentCategory.CREATE else 0.0
    reasoning_base = 0.4 if category is IntentCategory.SOLVE else 0.0
    knowledge_base = 0.3 if category is IntentCategory.LEARN else 0.0

    return IntentSignals(
        reasoning=_score(reasoning_base, _hits(normalized_text, _REASONING)),
        creativity=_score(creativity_base, _hits(normalized_text, _CREATIVITY)),
        knowledge=_score(knowledge_base, _hits(normalized_text, _KNOWLEDGE)),
        stakes=_score(0.0, _hits(normalized_text, _STAKES)),
    )
