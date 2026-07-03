"""Production guardrails: the difference between "the API is up" and "the API
is answering for real". Covers the Gateway's provider-mode detection and the
AXIOMN_REQUIRE_REAL_PROVIDER strict startup check that refuses to serve
simulated answers as if they were real.
"""
import pytest

from axiomn.gateway.catalog import default_catalog
from axiomn.gateway.handler import GatewayHandler, build_default_gateway
from axiomn.gateway.providers import AnthropicClient, ModelClient, OpenAIClient, SimulatedClient


def _gateway(anthropic: ModelClient, openai: ModelClient) -> GatewayHandler:
    return GatewayHandler(
        catalog=default_catalog(), clients={"anthropic": anthropic, "openai": openai}
    )


def test_provider_mode_real():
    gw = _gateway(AnthropicClient(api_key="x"), OpenAIClient(api_key="y"))
    assert gw.provider_mode() == "real"


def test_provider_mode_simulated():
    gw = _gateway(SimulatedClient(), SimulatedClient())
    assert gw.provider_mode() == "simulated"


def test_provider_mode_mixed():
    gw = _gateway(AnthropicClient(api_key="x"), SimulatedClient())
    assert gw.provider_mode() == "mixed"


def test_build_default_gateway_is_simulated_without_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AXIOMN_REQUIRE_REAL_PROVIDER", raising=False)
    assert build_default_gateway().provider_mode() == "simulated"


def test_require_real_provider_refuses_to_start_without_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AXIOMN_REQUIRE_REAL_PROVIDER", "1")
    with pytest.raises(RuntimeError, match="simulated"):
        build_default_gateway()


def test_require_real_provider_starts_when_mixed_is_still_refused(monkeypatch):
    # Only one key: one provider real, one simulated -> 'mixed' is not safe.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AXIOMN_REQUIRE_REAL_PROVIDER", "1")
    with pytest.raises(RuntimeError, match="mixed"):
        build_default_gateway()


def test_require_real_provider_ok_with_all_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    monkeypatch.setenv("AXIOMN_REQUIRE_REAL_PROVIDER", "1")
    gw = build_default_gateway()  # must not raise
    assert gw.provider_mode() == "real"
