"""Quality measurement: the missing half of "cheaper *without visible loss*".

AXIOMN could always prove cost went down. It could not prove quality held — so
"X% cheaper, same quality" was half-measured, half-asserted. This module closes
that gap with a cheap, deterministic **quality proxy**: a 0..1 score for each
execution's output, plus a one-line reason.

It is deliberately a proxy, not a judge model (no ML, no extra LLM call, no
latency): it catches the failure modes that actually destroy value — an empty
answer, a placeholder/stub that isn't a real answer, a provider failure, a
sandbox run that didn't verify. It feeds two things:

* the Router's trust loop (a low-quality outcome lowers that route's score, so
  the system *learns away* from routes that answer badly — the closed loop), and
* `GET /v1/metrics`, so savings are always reported next to a quality number
  and can never be read as savings from simply answering worse.

The thresholds are hand-tuned and easy to change; this is the transparent shape
a learned evaluator would later slot into behind the same `assess_quality`
contract.
"""
from __future__ import annotations

from dataclasses import dataclass

# Outputs that are structurally "not a real answer" — placeholders the pipeline
# emits when a tier is a stub or a backend was unavailable. Scored low on
# purpose: this is exactly the honesty the metric exists to enforce.
_STUB_MARKERS = ("[local]", "[simulated:", "[cloud-stub]", "[sandbox-unavailable]")


@dataclass
class QualityAssessment:
    score: float  # 0.0 (worthless) .. 1.0 (substantive)
    reason: str


def assess_quality(output: str, success: bool, metadata: dict | None = None) -> QualityAssessment:
    """Score an execution's output with deterministic proxies.

    Never raises and never calls a model — safe to run on every request.
    """
    metadata = metadata or {}
    text = (output or "").strip()

    if not text:
        return QualityAssessment(0.0, "empty output")

    if any(marker in text for marker in _STUB_MARKERS):
        return QualityAssessment(0.2, "placeholder/stub output, not a real answer")

    if "[gateway]" in text and "failed" in text:
        return QualityAssessment(0.1, "gateway/provider failure")

    # A sandboxed run carries its own verdict — trust the proof, not the prose.
    verity = metadata.get("verity")
    if isinstance(verity, dict) and verity.get("available"):
        if verity.get("verified") and verity.get("exit_code") == 0:
            return QualityAssessment(1.0, "sandboxed run verified")
        return QualityAssessment(0.3, "sandboxed run failed verification")

    if not success:
        return QualityAssessment(0.3, "tool reported failure")

    if len(text) < 8:
        return QualityAssessment(0.5, "suspiciously short output")

    return QualityAssessment(0.9, "substantive answer")
