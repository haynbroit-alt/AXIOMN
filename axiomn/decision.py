"""The negotiator's voice: explain each routing decision from the *client's*
side.

AXIOMN already computes everything a decision needs — the expected value of a
strong answer, the confidence and ambiguity of the reading, the cost against the
flagship baseline, and which model the Gateway picked and why. What it lacked was
a way to *say* it: not "model X was chosen" but "I spent up here because getting
this wrong would cost you, and I'm confident enough to commit — though I did
hesitate between two readings."

`explain_decision` turns those numbers into a small, honest arbitration
statement. It is deterministic and offline; it invents nothing the router didn't
already decide. This is what makes AXIOMN read as an agent defending the user's
interests rather than a black-box switch.
"""
from __future__ import annotations

from .intent.schema import Intent
from .router.router import Route

# Above this, we say the request "merits real intelligence"; below, it doesn't.
_HIGH_VALUE = 0.5
# Above this ambiguity, the reading is genuinely uncertain and worth flagging.
_NOTABLE_AMBIGUITY = 0.3


def _dominant_signal(intent: Intent) -> str | None:
    """The single dimension that most drove the value, for a human reason."""
    s = intent.signals
    ranked = sorted(
        [("reasoning", s.reasoning), ("creativity", s.creativity),
         ("knowledge", s.knowledge), ("stakes", s.stakes)],
        key=lambda kv: kv[1],
        reverse=True,
    )
    top, score = ranked[0]
    return top if score > 0 else None


def explain_decision(
    intent: Intent,
    route: Route,
    demand: int,
    *,
    cost: float,
    baseline_cost: float,
    model: str | None = None,
    model_reason: str | None = None,
) -> dict:
    """Build a client-facing arbitration for one routing decision.

    Returns a dict with a `headline` (one line), the `why` behind the spend,
    a `confidence` note, an optional `doubt` (null when the reading is crisp),
    and a `tradeoff` framing cost against the no-routing baseline.
    """
    dominant = _dominant_signal(intent)
    reason_bits = {
        "stakes": "getting this wrong would be costly",
        "creativity": "it calls for real creative work",
        "reasoning": "it needs genuine reasoning",
        "knowledge": "it demands real depth of knowledge",
    }

    if route is Route.HUMAN_QUEUE:
        headline = "Handed to a human — not guessing"
        why = (
            "The best decision here is not to spend a model on a coin-flip: "
            "this is better answered (or clarified) by a person."
        )
    elif route is Route.LOCAL_AI:
        headline = "Kept it cheap — no need to overpay"
        why = (
            f"Low expected value ({intent.value}); a fast local model handles "
            "this at no cost, so your budget is saved for what matters."
        )
    else:  # CLOUD_AI
        headline = "Spent up — this one is worth it"
        driver = reason_bits.get(dominant or "", "it merits real intelligence")
        why = (
            f"High expected value ({intent.value}) because {driver}; demand {demand}/10 "
            "earns a stronger model rather than the cheapest one."
        )
        if model:
            why += f" The Gateway picked {model}"
            why += f" — {model_reason}." if model_reason else "."

    # Confidence and — the honest part — doubt.
    confidence_note = (
        f"Confident ({intent.confidence}) this is a {intent.category.value} request."
        if intent.confidence >= 0.6
        else f"Only tentatively ({intent.confidence}) read as a {intent.category.value} request."
    )
    doubt = None
    if intent.ambiguity >= _NOTABLE_AMBIGUITY:
        doubt = (
            f"I hesitated: the intent is ambiguous ({intent.ambiguity}), so this "
            "could reasonably be read another way — tell me if I misjudged it."
        )

    saved = baseline_cost - cost
    if baseline_cost > 0 and saved > 0:
        pct = round(100 * saved / baseline_cost)
        tradeoff = f"{cost} vs {baseline_cost} at the flagship — about {pct}% cheaper than always going premium."
    elif route is Route.HUMAN_QUEUE:
        tradeoff = "No model spend; a person's time instead of a confident-sounding guess."
    else:
        tradeoff = f"Priced at {cost}; the flagship baseline for this request is {baseline_cost}."

    return {
        "headline": headline,
        "why": why,
        "confidence": intent.confidence,
        "confidence_note": confidence_note,
        "doubt": doubt,
        "tradeoff": tradeoff,
    }
