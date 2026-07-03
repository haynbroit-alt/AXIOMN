"""The AXIOMN -> SIOS audit edge: every decision becomes a canonical,
SHA-256-hashed event that never carries the user's raw text, shipped to SIOS
opt-in and fail-open.
"""
import hashlib
import json

import httpx

from axiomn.audit import (
    AuditEvent,
    CompositeAuditSink,
    HttpAuditSink,
    LoggingAuditSink,
    build_audit_sink,
    build_event,
)


def _event(text: str = "print(2 ** 10)", **over) -> AuditEvent:
    base = dict(
        payload_text=text, category="automate", language="en", route="local_ai",
        tool="verity_sandbox", success=True, cost=0.0, baseline_cost=0.03,
        latency_ms=12.5, model=None,
    )
    base.update(over)
    return build_event(**base)


def test_payload_text_is_hashed_never_stored():
    event = _event("secret user input")
    assert event.payload_hash == hashlib.sha256(b"secret user input").hexdigest()
    # The raw text must not appear anywhere in the serialized event.
    assert "secret user input" not in json.dumps(event.to_dict())


def test_content_hash_is_deterministic_and_sensitive():
    a = _event("same", latency_ms=10.0)
    b = _event("same", latency_ms=10.0)
    # ts differs run-to-run, so pin it to compare the decision content only.
    a.ts = b.ts = 0.0
    a.__post_init__()
    b.__post_init__()
    assert a.content_hash == b.content_hash

    c = _event("same", latency_ms=10.0)
    c.ts = 0.0
    c.route = "cloud_ai"
    c.__post_init__()
    assert c.content_hash != a.content_hash


def test_http_sink_posts_the_event():
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"ok": True})

    sink = HttpAuditSink("https://sios.example", transport=httpx.MockTransport(responder))
    sink.emit(_event())
    sink.close()

    assert seen["url"] == "https://sios.example/v1/audit/decision"
    assert seen["body"]["route"] == "local_ai"
    assert seen["body"]["content_hash"]


def test_http_sink_fails_open_when_sios_down():
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    sink = HttpAuditSink("https://sios.example", transport=httpx.MockTransport(responder))
    sink.emit(_event())  # must not raise
    sink.close()


def test_build_audit_sink_is_log_only_without_env(monkeypatch):
    monkeypatch.delenv("AXIOMN_AUDIT_URL", raising=False)
    assert isinstance(build_audit_sink(), LoggingAuditSink)


def test_build_audit_sink_adds_http_when_configured(monkeypatch):
    monkeypatch.setenv("AXIOMN_AUDIT_URL", "https://sios.example")
    sink = build_audit_sink()
    assert isinstance(sink, CompositeAuditSink)


def test_logging_sink_emits_without_error():
    LoggingAuditSink().emit(_event())  # smoke: structured log path
