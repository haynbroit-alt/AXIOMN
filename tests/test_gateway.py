import pytest

from axiomn.gateway.catalog import ModelCatalog, ModelProfile, default_catalog
from axiomn.gateway.handler import GatewayHandler, build_default_gateway
from axiomn.gateway.providers import SimulatedClient
from axiomn.intent.schema import Intent, IntentCategory


def _intent(difficulty: int) -> Intent:
    return Intent(
        text="some request",
        category=IntentCategory.LEARN,
        topic="some request",
        language="en",
        difficulty=difficulty,
        confidence=0.8,
    )


def _catalog() -> ModelCatalog:
    return default_catalog()


def test_easy_request_selects_the_cheapest_adequate_model():
    profile, reason = _catalog().select(_intent(difficulty=3))
    assert profile.name == "claude-haiku"
    assert "cheapest adequate" in reason


def test_mid_difficulty_skips_models_that_are_not_good_enough():
    profile, _ = _catalog().select(_intent(difficulty=7))
    assert profile.name == "gpt-4o"  # haiku (quality 6) no longer qualifies


def test_hard_request_selects_the_flagship():
    profile, _ = _catalog().select(_intent(difficulty=9))
    assert profile.name == "claude-opus"


def test_impossible_difficulty_falls_back_to_most_capable_with_honest_reason():
    profile, reason = _catalog().select(_intent(difficulty=10))
    assert profile.name == "claude-opus"
    assert "exceeds every model" in reason


def test_flagship_is_the_highest_quality_model():
    assert _catalog().flagship().name == "claude-opus"


def test_handler_reports_model_cost_baseline_and_reason():
    handler = GatewayHandler(clients={"anthropic": SimulatedClient(), "openai": SimulatedClient()})
    result = handler.run(_intent(difficulty=2))

    assert result.success is True
    # The wire model_id (not the display name) reaches the provider client.
    assert result.output.startswith("[simulated:claude-haiku-4-5]")
    assert result.metadata["model"] == "claude-haiku"
    assert result.metadata["model_id"] == "claude-haiku-4-5"
    assert result.metadata["provider"] == "anthropic"
    assert result.metadata["cost"] == 0.01
    assert result.metadata["baseline_cost"] == 0.15
    assert "cheapest adequate" in result.metadata["selection_reason"]


def test_default_catalog_uses_real_api_model_ids_on_the_wire():
    # Regression test for the production 404: Anthropic's Messages API
    # rejects display names like "claude-haiku" — the wire ID must be a
    # real, current model identifier.
    by_name = {p.name: p for p in default_catalog().profiles}
    assert by_name["claude-haiku"].model_id == "claude-haiku-4-5"
    assert by_name["claude-opus"].model_id == "claude-opus-4-8"
    assert by_name["gpt-4o"].model_id == "gpt-4o"  # OpenAI's public ID doubles as display


def test_model_id_defaults_to_name_when_not_given():
    profile = ModelProfile(name="local-llama", provider="local", quality=5, cost_per_call=0.0, latency_ms=100)
    assert profile.model_id == "local-llama"


def test_provider_failure_is_an_honest_failure_not_a_fake_answer():
    class ExplodingClient:
        def complete(self, model, intent):
            raise ConnectionError("provider down")

    handler = GatewayHandler(clients={"anthropic": ExplodingClient(), "openai": ExplodingClient()})
    result = handler.run(_intent(difficulty=2))

    assert result.success is False  # feeds the Router's trust score downward
    assert "failed" in result.output
    assert result.metadata["model"] == "claude-haiku"


def test_handler_refuses_a_catalog_with_unconfigured_providers():
    with pytest.raises(ValueError, match="openai"):
        GatewayHandler(clients={"anthropic": SimulatedClient()})


def test_default_gateway_without_keys_uses_labeled_simulated_clients(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = build_default_gateway().run(_intent(difficulty=2))
    # The honesty rule: a simulated answer must announce itself.
    assert result.output.startswith("[simulated:")


def test_swapping_providers_is_a_catalog_edit_not_a_rewrite():
    # The portability promise: the same request, a different vendor —
    # nothing but the catalog changes.
    catalog = ModelCatalog(
        [ModelProfile(name="local-llama", provider="local", quality=8, cost_per_call=0.0, latency_ms=200)]
    )

    class LocalClient:
        def complete(self, model, intent):
            return f"[{model}] local answer"

    handler = GatewayHandler(catalog=catalog, clients={"local": LocalClient()})
    result = handler.run(_intent(difficulty=5))
    assert result.output == "[local-llama] local answer"
    assert result.metadata["provider"] == "local"
