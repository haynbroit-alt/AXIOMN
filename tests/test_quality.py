"""The quality proxy and the closed feedback loop: the other half of "cheaper
without visible loss". Deterministic and offline.
"""
from axiomn.quality import assess_quality
from axiomn.router.router import Route, Router


def test_empty_output_is_worthless():
    assert assess_quality("", True, {}).score == 0.0


def test_stub_output_scores_low_even_when_successful():
    # The local heuristic tier returns a template, not a real answer — the
    # metric must call that out rather than count it as a good answer.
    q = assess_quality("[local] learn answer for: black holes", True, {})
    assert q.score <= 0.3
    q2 = assess_quality("[simulated:gpt-4o] create answer for: x", True, {})
    assert q2.score <= 0.3


def test_gateway_failure_scores_lowest_band():
    assert assess_quality("[gateway] gpt-4o failed: timeout", False, {}).score <= 0.2


def test_verified_sandbox_run_is_top_quality():
    q = assess_quality("1024\n", True, {"verity": {"available": True, "verified": True, "exit_code": 0}})
    assert q.score == 1.0


def test_unverified_sandbox_run_scores_low():
    q = assess_quality("boom", True, {"verity": {"available": True, "verified": False, "exit_code": 1}})
    assert q.score <= 0.3


def test_substantive_answer_scores_high():
    assert assess_quality("A black hole forms when a massive star collapses...", True, {}).score >= 0.8


def test_quality_drives_the_trust_loop_down_for_stubs():
    # The closed loop: repeatedly returning low-quality answers on a route
    # should pull that route's trust score down over time.
    router = Router()
    before = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)
    for _ in range(10):
        router.record_outcome(Route.LOCAL_AI, success=True, quality=0.2)
    after = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)
    assert after < before


def test_high_quality_keeps_trust_high():
    router = Router()
    for _ in range(10):
        router.record_outcome(Route.CLOUD_AI, success=True, quality=1.0)
    after = next(p.trust_score for p in router.profiles if p.route == Route.CLOUD_AI)
    assert after > 0.9


def test_record_outcome_still_accepts_bare_success():
    # Backward compatible: no quality given -> success flag drives the EMA.
    router = Router()
    router.record_outcome(Route.LOCAL_AI, success=False)  # must not raise
