from axiomn.execution.engine import ExecutionEngine
from axiomn.intent.schema import Intent, IntentCategory
from axiomn.router.router import Route


def _intent() -> Intent:
    return Intent(text="x", category=IntentCategory.LEARN, topic="x", language="en", difficulty=1, confidence=0.5)


def test_execution_dispatches_to_local_backend():
    result = ExecutionEngine().execute(Route.LOCAL_AI, _intent())
    assert result.startswith("[local]")


def test_execution_dispatches_to_cloud_backend():
    result = ExecutionEngine().execute(Route.CLOUD_AI, _intent())
    assert result.startswith("[cloud-stub]")


def test_execution_dispatches_to_human_queue():
    result = ExecutionEngine().execute(Route.HUMAN_QUEUE, _intent())
    assert "Queued" in result


def test_custom_backend_can_be_injected():
    class FakeBackend:
        def run(self, intent):
            return "custom"

    engine = ExecutionEngine(local=FakeBackend())
    assert engine.execute(Route.LOCAL_AI, _intent()) == "custom"
