"""The routing-quality benchmark (ROADMAP, Architecture #4): a fixed,
labeled corpus of intents, with the scored Router measured against the
naive fixed-threshold baseline it replaced in PR #2. This turns "dynamic
routing is better" from a claim into a number, printed on every run:

    pytest tests/test_routing_benchmark.py -s

The label is the route a product owner would want, given everything the
intent says — not just its difficulty. The baseline can only see
difficulty; the scored router also sees category, ambiguity, and cost,
which is exactly where the corpus makes it win.
"""
from axiomn.intent.schema import Intent, IntentCategory
from axiomn.router.router import Route, Router


def _intent(difficulty: int, category=IntentCategory.LEARN, ambiguity: float = 0.0) -> Intent:
    return Intent(
        text="x", category=category, topic="x", language="en",
        difficulty=difficulty, confidence=0.8, ambiguity=ambiguity,
    )


def _baseline_route(intent: Intent) -> Route:
    """The pre-PR#2 policy: fixed difficulty thresholds, blind to category,
    ambiguity, and cost."""
    if intent.difficulty <= 4:
        return Route.LOCAL_AI
    if intent.difficulty <= 8:
        return Route.CLOUD_AI
    return Route.HUMAN_QUEUE


# (intent, the route a product owner would want, why)
CORPUS: list[tuple[Intent, Route, str]] = [
    # Trivial requests stay local — both policies should get these.
    (_intent(1), Route.LOCAL_AI, "trivial lookup"),
    (_intent(2, IntentCategory.SOLVE), Route.LOCAL_AI, "trivial fix"),
    (_intent(3, IntentCategory.CREATE), Route.LOCAL_AI, "short creative ask"),
    (_intent(4), Route.LOCAL_AI, "upper edge of local capability"),
    # Mid difficulty goes to a cloud model — both should get these.
    (_intent(5), Route.CLOUD_AI, "beyond local capability"),
    (_intent(6, IntentCategory.SOLVE), Route.CLOUD_AI, "real debugging"),
    (_intent(7, IntentCategory.CREATE), Route.CLOUD_AI, "substantial writing"),
    (_intent(8), Route.CLOUD_AI, "hard reasoning"),
    # Expert-only difficulty needs a human — both should get these.
    (_intent(9), Route.HUMAN_QUEUE, "beyond every model's capability"),
    (_intent(10), Route.HUMAN_QUEUE, "expert-only"),
    # Where the scored router should win: CONNECT means "find me a person"
    # regardless of difficulty — the baseline sends these to a machine.
    (_intent(1, IntentCategory.CONNECT), Route.HUMAN_QUEUE, "easy connect is still a human ask"),
    (_intent(3, IntentCategory.CONNECT), Route.HUMAN_QUEUE, "connect at low difficulty"),
    (_intent(6, IntentCategory.CONNECT), Route.HUMAN_QUEUE, "connect at mid difficulty"),
    # Where the scored router should win: a genuinely ambiguous request is
    # cheaper to clarify with a human than to guess at with a model.
    (_intent(5, ambiguity=0.9), Route.HUMAN_QUEUE, "coin-flip classification, mid difficulty"),
    (_intent(6, ambiguity=0.95), Route.HUMAN_QUEUE, "near-tie classification"),
    # And ambiguity must NOT hijack crisp requests.
    (_intent(5, ambiguity=0.1), Route.CLOUD_AI, "crisp mid-difficulty request"),
]


def _accuracy(route_fn) -> float:
    hits = sum(1 for intent, expected, _ in CORPUS if route_fn(intent) == expected)
    return hits / len(CORPUS)


def test_scored_router_beats_the_fixed_threshold_baseline():
    router = Router()
    scored = _accuracy(router.route)
    baseline = _accuracy(_baseline_route)

    print(
        f"\nrouting-quality benchmark ({len(CORPUS)} labeled intents): "
        f"scored router {scored:.0%} vs fixed-threshold baseline {baseline:.0%}"
    )
    assert scored > baseline, (
        f"scored router ({scored:.0%}) must beat the baseline ({baseline:.0%})"
    )


def test_scored_router_is_perfect_on_the_corpus():
    # Stronger than beating the baseline: every current guarantee holds at
    # once. If a routing change breaks any labeled case, this names it.
    router = Router()
    misses = [
        (why, expected.value, router.route(intent).value)
        for intent, expected, why in CORPUS
        if router.route(intent) != expected
    ]
    assert misses == [], f"misrouted cases (why, expected, got): {misses}"
