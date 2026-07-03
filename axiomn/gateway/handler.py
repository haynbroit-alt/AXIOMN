"""The Gateway: AXIOMN's first product surface, as a plain `ToolHandler`.

It slots into the existing kernel unchanged — the Router still decides
*whether* a request deserves a cloud model; the Gateway decides *which*
model, calls it through the provider-agnostic client contract, and
reports what it chose, what it cost, and why in `ToolResult.metadata`.
The savings baseline (`baseline_cost`) is what the request would have
cost on the flagship model — the common no-routing setup — so
`GET /v1/metrics` can report measured savings instead of a marketing
claim.
"""
import os

from ..intent.schema import Intent
from ..models.tools import ToolResult
from .catalog import ModelCatalog, default_catalog
from .providers import AnthropicClient, ModelClient, OpenAIClient, SimulatedClient


class GatewayHandler:
    def __init__(self, catalog: ModelCatalog | None = None, clients: dict[str, ModelClient] | None = None):
        self.catalog = catalog or default_catalog()
        self.clients = clients if clients is not None else {}
        missing = {p.provider for p in self.catalog.profiles} - set(self.clients)
        if missing:
            raise ValueError(f"No client configured for provider(s): {sorted(missing)}")

    def provider_mode(self) -> str:
        """Whether this Gateway can produce real answers or only simulated ones.

        ``real`` — every configured provider is a live client.
        ``simulated`` — every provider is the offline `SimulatedClient`.
        ``mixed`` — some real, some simulated (a request routed to a simulated
        provider still comes back `[simulated:...]`, so this is *not* a
        production-safe state; the strict startup check below treats only
        ``real`` as safe).
        """
        simulated = [isinstance(c, SimulatedClient) for c in self.clients.values()]
        if not any(simulated):
            return "real"
        if all(simulated):
            return "simulated"
        return "mixed"

    def run(self, intent: Intent) -> ToolResult:
        profile, reason = self.catalog.select(intent)
        metadata = {
            "model": profile.name,
            "model_id": profile.model_id,
            "provider": profile.provider,
            "cost": profile.cost_per_call,
            "baseline_cost": self.catalog.flagship().cost_per_call,
            "selection_reason": reason,
        }
        try:
            # The wire ID, never the display name — providers 404 on the latter.
            output = self.clients[profile.provider].complete(profile.model_id, intent)
        except Exception as exc:  # provider/network failure -> honest failure, trust feedback
            return ToolResult(
                output=f"[gateway] {profile.name} failed: {exc}",
                success=False,
                metadata=metadata,
            )
        return ToolResult(output=output, metadata=metadata)


def build_default_gateway() -> GatewayHandler:
    """Real provider clients when API keys are configured (`ANTHROPIC_API_KEY`,
    `OPENAI_API_KEY`), clearly-labeled simulated ones when not — so the
    Gateway's selection, transparency, and savings measurement are always
    demonstrable, but a simulated answer is never presentable as real."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    clients: dict[str, ModelClient] = {
        "anthropic": AnthropicClient(anthropic_key) if anthropic_key else SimulatedClient(),
        "openai": OpenAIClient(openai_key) if openai_key else SimulatedClient(),
    }
    gateway = GatewayHandler(catalog=default_catalog(), clients=clients)
    # Production guardrail: with AXIOMN_REQUIRE_REAL_PROVIDER set, refuse to
    # start unless every provider is a live client. This is the difference
    # between "the API is up" and "the API is answering for real" — it stops a
    # deploy from silently serving `[simulated:...]` because a key was forgotten.
    if os.environ.get("AXIOMN_REQUIRE_REAL_PROVIDER", "0").lower() in ("1", "true"):
        mode = gateway.provider_mode()
        if mode != "real":
            raise RuntimeError(
                "AXIOMN_REQUIRE_REAL_PROVIDER is set but the Gateway is in "
                f"'{mode}' mode: no real answers without ANTHROPIC_API_KEY and "
                "OPENAI_API_KEY configured. Refusing to start in a state that "
                "would serve simulated answers as if they were real."
            )
    return gateway
