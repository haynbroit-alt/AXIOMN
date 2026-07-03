"""Structured logging: one JSON object per line, with `extra=` fields promoted
to top-level keys and the current request id threaded in, so decisions are
queryable after the fact.
"""
import json
import logging

from axiomn.observability import (
    JsonFormatter,
    configure_logging,
    logger,
    request_id_var,
)


def _record(msg: str, **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="axiomn", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_promotes_extra_fields():
    formatted = JsonFormatter().format(_record("intent.routed", route="local_ai", cost=0.0))
    payload = json.loads(formatted)
    assert payload["message"] == "intent.routed"
    assert payload["level"] == "INFO"
    assert payload["route"] == "local_ai"
    assert payload["cost"] == 0.0


def test_json_formatter_includes_request_id_when_set():
    token = request_id_var.set("req-abc")
    try:
        payload = json.loads(JsonFormatter().format(_record("request.handled")))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "req-abc"


def test_json_formatter_omits_request_id_when_unset():
    # Default context has no request id -> the key is absent, not null.
    payload = json.loads(JsonFormatter().format(_record("startup")))
    assert "request_id" not in payload


def test_configure_logging_json_is_default(monkeypatch):
    monkeypatch.delenv("AXIOMN_LOG_FORMAT", raising=False)
    configure_logging()
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, JsonFormatter)
    assert logger.propagate is False


def test_configure_logging_text_mode(monkeypatch):
    monkeypatch.setenv("AXIOMN_LOG_FORMAT", "text")
    configure_logging()
    assert not isinstance(logger.handlers[0].formatter, JsonFormatter)
    # Restore JSON default so other tests/modules aren't affected by order.
    monkeypatch.setenv("AXIOMN_LOG_FORMAT", "json")
    configure_logging()
