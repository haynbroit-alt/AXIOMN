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

    def run(self, intent: Intent) -> ToolResult:
        profile, reason = self.catalog.select(intent)
        metadata = {
            "model": profile.name,
            "provider": profile.provider,
            "cost": profile.cost_per_call,
            "baseline_cost": self.catalog.flagship().cost_per_call,
            "selection_reason": reason,
        }
        try:
            output = self.clients[profile.provider].complete(profile.name, intent)
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
    return GatewayHandler(catalog=default_catalog(), clients=clients)
