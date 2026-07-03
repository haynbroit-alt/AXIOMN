"""Audit events: the AXIOMN → SIOS edge of the closed loop.

Every decision the runtime makes is emitted as a canonical, content-hashed
record — the same SHA-256 discipline SIOS/CPO and VERITY use — so a decision can
be audited and verified independently of AXIOMN. This is the first cross-system
arrow of the unified architecture (see UNIFIED_ARCHITECTURE.md): AXIOMN decides,
and hands SIOS a tamper-evident event to measure and prove.

Two deliberate boundaries:

* **Privacy first (RGPD / droit à l'oubli).** The user's text is never stored in
  the audit event — only its SHA-256 (`payload_hash`). The event carries the
  decision (route, model, cost, latency, success, proof), not the content.
* **Opt-in, fail-open transport.** The event is always logged (cheap, local).
  Shipping it to a SIOS ingest endpoint happens only when `AXIOMN_AUDIT_URL` is
  set, and a SIOS that is down degrades to log-only instead of taking a request
  with it — the runtime's decision must not depend on the auditor being up.

The event is intentionally *not* chained here: append-only ordering and the
ledger live on the SIOS side. AXIOMN's job is to emit a faithful, hashed record.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Optional, Protocol

import httpx

from .observability import logger, request_id_var


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(payload: dict) -> str:
    """Stable serialization so the same decision always hashes the same way."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class AuditEvent:
    """A single decision, reduced to what can be audited without the raw text."""

    ts: float
    payload_hash: str  # sha256 of the user's text — never the text itself
    category: str
    language: str
    route: str
    tool: str
    success: bool
    cost: float
    baseline_cost: float
    latency_ms: float
    model: Optional[str] = None
    model_reason: Optional[str] = None
    proof: Optional[dict] = None  # VERITY signature/action_id when code was run
    request_id: Optional[str] = None
    content_hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        body = {k: v for k, v in asdict(self).items() if k != "content_hash"}
        self.content_hash = _sha256(_canonical(body))

    def to_dict(self) -> dict:
        return asdict(self)


class AuditSink(Protocol):
    def emit(self, event: AuditEvent) -> None: ...


class LoggingAuditSink:
    """Always-on sink: writes the event as a structured `audit.decision` log."""

    def emit(self, event: AuditEvent) -> None:
        logger.info("audit.decision", extra=event.to_dict())


class HttpAuditSink:
    """Ships events to a SIOS ingest endpoint. Fail-open by construction."""

    def __init__(
        self,
        base_url: str,
        *,
        path: str = "/v1/audit/decision",
        timeout: float = 5.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.url = base_url.rstrip("/") + path
        self._client = httpx.Client(
            timeout=timeout, transport=transport, headers={"content-type": "application/json"}
        )

    def emit(self, event: AuditEvent) -> None:
        try:
            self._client.post(self.url, json=event.to_dict()).raise_for_status()
        except httpx.HTTPError as exc:
            # The auditor being unreachable must never break serving a request.
            logger.warning(
                "audit.sink_unavailable",
                extra={"error": str(exc), "content_hash": event.content_hash},
            )

    def close(self) -> None:
        self._client.close()


class CompositeAuditSink:
    def __init__(self, sinks: list[AuditSink]):
        self._sinks = sinks

    def emit(self, event: AuditEvent) -> None:
        for sink in self._sinks:
            sink.emit(event)


def build_audit_sink(
    base_url: Optional[str] = None,
    *,
    transport: Optional[httpx.BaseTransport] = None,
) -> AuditSink:
    """Log-only by default; also POST to SIOS when `AXIOMN_AUDIT_URL` is set."""
    import os

    url = base_url or os.environ.get("AXIOMN_AUDIT_URL")
    logging_sink: AuditSink = LoggingAuditSink()
    if not url:
        return logging_sink
    return CompositeAuditSink([logging_sink, HttpAuditSink(url, transport=transport)])


def build_event(
    *,
    payload_text: str,
    category: str,
    language: str,
    route: str,
    tool: str,
    success: bool,
    cost: float,
    baseline_cost: float,
    latency_ms: float,
    model: Optional[str] = None,
    model_reason: Optional[str] = None,
    proof: Optional[dict] = None,
) -> AuditEvent:
    """Assemble an `AuditEvent` from a decision, hashing the text for privacy."""
    return AuditEvent(
        ts=time.time(),
        payload_hash=_sha256(payload_text),
        category=category,
        language=language,
        route=route,
        tool=tool,
        success=success,
        cost=cost,
        baseline_cost=baseline_cost,
        latency_ms=round(latency_ms, 2),
        model=model,
        model_reason=model_reason,
        proof=proof,
        request_id=request_id_var.get(),
    )
