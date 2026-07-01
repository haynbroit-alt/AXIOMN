"""The Execution Layer: dispatches an Intent to the backend chosen by the Router."""
from ..intent.schema import Intent
from ..models.backends import Backend, CloudBackendStub, HumanQueueBackend, LocalHeuristicBackend
from ..router.router import Route


class ExecutionEngine:
    def __init__(
        self,
        local: Backend | None = None,
        cloud: Backend | None = None,
        human: Backend | None = None,
    ):
        self._backends: dict[Route, Backend] = {
            Route.LOCAL_AI: local or LocalHeuristicBackend(),
            Route.CLOUD_AI: cloud or CloudBackendStub(),
            Route.HUMAN_QUEUE: human or HumanQueueBackend(),
        }

    def execute(self, route: Route, intent: Intent) -> str:
        return self._backends[route].run(intent)
