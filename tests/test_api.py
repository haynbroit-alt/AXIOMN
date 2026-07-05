from fastapi.testclient import TestClient

from axiomn.api.main import DEFAULT_TTL_SECONDS, _queue_ttl_seconds, app

client = TestClient(app)


def test_health_reports_status_and_serving_version():
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    # The deploy-observability contract: health always names the build
    # version actually serving, so "did the redeploy take?" is answerable
    # from outside.
    assert data["version"] == "0.2.1"
    # Honesty signal: without provider keys the runtime answers in simulated
    # mode, and health says so instead of hiding it.
    assert data["provider_mode"] in {"real", "simulated", "mixed"}
    # Every response carries a correlation id from the request-context middleware.
    assert response.headers["X-Request-ID"]


def test_request_id_is_echoed_when_supplied():
    response = client.get("/health", headers={"X-Request-ID": "trace-42"})
    assert response.headers["X-Request-ID"] == "trace-42"


def test_estimate_projects_savings_on_a_batch_without_executing():
    # A mix of easy (local) and hard (cloud) prompts should show real savings
    # vs the all-flagship baseline — with no provider keys configured.
    resp = client.post(
        "/v1/estimate",
        json={"texts": ["Explain how black holes form", "hi", "what is 2+2"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["requests"] == 3
    assert len(data["items"]) == 3
    assert data["summary"]["baseline_cost"] >= data["summary"]["projected_cost"]
    assert 0.0 <= data["summary"]["savings_rate"] <= 1.0
    for item in data["items"]:
        assert item["route"] in {"local_ai", "cloud_ai", "human_queue"}
        # Invariant: no request is ever projected above its own baseline — a
        # human escalation makes no savings claim, it never shows as a loss.
        assert item["cost"] <= item["baseline_cost"]


def test_estimate_rejects_oversized_or_empty_batches():
    # Unauthenticated endpoint: the batch is bounded so it can't be used to
    # force unbounded classification work.
    assert client.post("/v1/estimate", json={"texts": []}).status_code == 422
    assert client.post("/v1/estimate", json={"texts": ["x"] * 101}).status_code == 422
    assert client.post("/v1/estimate", json={"texts": ["x" * 4001]}).status_code == 422


def test_health_includes_image_ref_when_platform_provides_one(monkeypatch):
    monkeypatch.setenv("FLY_IMAGE_REF", "registry.fly.io/axiomn:deployment-123")
    data = client.get("/health").json()
    assert data["build"] == "registry.fly.io/axiomn:deployment-123"


def test_intent_endpoint_returns_full_pipeline_result():
    response = client.post("/intent", json={"text": "Explain how black holes form"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "learn"
    assert data["route"] in {"local_ai", "cloud_ai", "human_queue"}
    assert data["result"]
    assert data["tool"]
    assert data["execution_time_ms"] >= 0
    assert 0.0 <= data["ambiguity"] <= 1.0
    assert data["action"]["type"] == "voice_reply"
    assert data["action"]["payload"]["text"] == data["result"]


def test_connect_intent_escalates_to_human_and_yields_await_human_action():
    # CONNECT always routes to human_queue, which overrides the category's
    # usual action mapping (open_url) with await_human — there's no
    # instant answer to hand back yet.
    response = client.post("/intent", json={"text": "Trouve un expert en droit fiscal pour moi"})
    data = response.json()
    assert data["route"] == "human_queue"
    assert data["action"]["type"] == "await_human"


def test_cloud_routed_request_goes_through_the_gateway_with_explainable_model_choice():
    # A crisp SOLVE request (fix/debug/error keywords) long enough plus a
    # "distributed system" complexity marker -> difficulty ~6: beyond
    # local_ai's capability, well within cloud_ai's, unambiguous enough
    # not to escalate to a human.
    text = (
        "Help me debug and fix the intermittent caching error in my distributed system "
        "where repeated requests sometimes return stale data after a node restarts"
    )
    data = client.post("/intent", json={"text": text}).json()

    assert data["route"] == "cloud_ai"
    assert data["tool"] == "gateway"
    assert data["model"]  # which model was chosen...
    assert data["model_reason"]  # ...and why — the choice is always explainable
    # No API keys in the test environment: the answer must announce itself
    # as simulated, never pass for a real model's.
    assert data["result"].startswith("[simulated:")


def test_locally_resolved_requests_report_measured_savings():
    before = client.get("/v1/metrics").json()
    before_saved = before.get("savings", {}).get("saved", 0.0)

    client.post("/intent", json={"text": "Explain how black holes form"})

    savings = client.get("/v1/metrics").json()["savings"]
    # A local resolution costs 0 but would have cost flagship money in the
    # common everything-to-the-premium-model setup: measured, not claimed.
    assert savings["saved"] > before_saved
    assert 0.0 < savings["rate"] <= 1.0


def test_intent_endpoint_rejects_missing_text():
    response = client.post("/intent", json={})
    assert response.status_code == 422


def test_intent_endpoint_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("AXIOMN_API_KEYS", "secret123")
    assert client.post("/v1/intent", json={"text": "hello"}).status_code == 401


def test_operator_answer_endpoint_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("AXIOMN_API_KEYS", "secret123")
    response = client.post("/v1/queue/any-id/answer", json={"text": "hi"})
    assert response.status_code == 401  # auth is checked before ticket lookup


def test_intent_endpoint_accepts_correct_api_key(monkeypatch):
    monkeypatch.setenv("AXIOMN_API_KEYS", "secret123")
    response = client.post(
        "/v1/intent", json={"text": "hello"}, headers={"X-API-Key": "secret123"}
    )
    assert response.status_code == 200


def test_intent_endpoint_enforces_rate_limit():
    import axiomn.api.main as main_module

    # A dedicated client id (via X-API-Key, which doubles as the rate-limit
    # bucket key) keeps this test's budget isolated from every other test.
    headers = {"X-API-Key": "rate-limit-test-client"}
    original_max = main_module.rate_limiter.max_requests
    main_module.rate_limiter.max_requests = 2
    try:
        client.post("/v1/intent", json={"text": "hello"}, headers=headers)
        client.post("/v1/intent", json={"text": "hello"}, headers=headers)
        response = client.post("/v1/intent", json={"text": "hello"}, headers=headers)
        assert response.status_code == 429
    finally:
        main_module.rate_limiter.max_requests = original_max


# --- Every question has an answer: unhandled errors and queue TTL wiring ---


def test_unhandled_pipeline_error_still_returns_a_structured_answer(monkeypatch):
    import axiomn.api.main as main_module

    def _boom(_text):
        raise RuntimeError("simulated pipeline crash")

    monkeypatch.setattr(main_module.intent_engine, "classify", _boom)
    # Starlette's ServerErrorMiddleware always re-raises the original exception
    # after invoking a registered handler, specifically so TestClient can
    # surface it for debugging (raise_server_exceptions=True by default) — a
    # real HTTP client only ever sees the handler's response. Opt out here to
    # assert on that actual response instead of the re-raised exception.
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.post("/v1/intent", json={"text": "hello"})

    # Never a bare, undocumented crash: still a clear, actionable JSON body.
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "internal_error"
    assert data["message"]
    assert response.headers["X-Request-ID"]


def test_queue_ttl_seconds_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("AXIOMN_QUEUE_TTL_SECONDS", raising=False)
    assert _queue_ttl_seconds() == DEFAULT_TTL_SECONDS


def test_queue_ttl_seconds_disabled_by_zero_or_negative(monkeypatch):
    monkeypatch.setenv("AXIOMN_QUEUE_TTL_SECONDS", "0")
    assert _queue_ttl_seconds() is None
    monkeypatch.setenv("AXIOMN_QUEUE_TTL_SECONDS", "-5")
    assert _queue_ttl_seconds() is None


def test_queue_ttl_seconds_respects_env_override(monkeypatch):
    monkeypatch.setenv("AXIOMN_QUEUE_TTL_SECONDS", "42")
    assert _queue_ttl_seconds() == 42.0
