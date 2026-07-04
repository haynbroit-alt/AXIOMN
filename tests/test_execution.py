from axiomn.execution.engine import ExecutionEngine
from axiomn.intent.schema import Intent, IntentCategory
from axiomn.models.tools import Tool, ToolRegistry, ToolResult
from axiomn.router.router import Route, Router


def _intent(category: IntentCategory = IntentCategory.LEARN) -> Intent:
    return Intent(text="x", category=category, topic="x", language="en", difficulty=1, confidence=0.5)


def test_execution_dispatches_to_local_tool():
    outcome = ExecutionEngine().execute(Route.LOCAL_AI, _intent())
    assert outcome.output.startswith("[local]")
    assert outcome.success is True
    assert outcome.latency_ms >= 0


def test_execution_dispatches_to_cloud_tool():
    outcome = ExecutionEngine().execute(Route.CLOUD_AI, _intent())
    assert outcome.output.startswith("[cloud-stub]")


def test_execution_dispatches_to_human_queue_tool():
    outcome = ExecutionEngine().execute(Route.HUMAN_QUEUE, _intent())
    assert "Queued" in outcome.output


def test_custom_tool_can_be_injected():
    class FakeHandler:
        def run(self, intent):
            return ToolResult(output="custom")

    registry = ToolRegistry()
    registry.register(Tool(name="fake", route=Route.LOCAL_AI, handler=FakeHandler()))
    outcome = ExecutionEngine(registry=registry).execute(Route.LOCAL_AI, _intent())
    assert outcome.output == "custom"
    assert outcome.tool_name == "fake"


def test_execution_reports_quality_back_to_router():
    """A genuinely good answer raises the route's trust (the loop is wired,
    and it learns from measured quality)."""
    router = Router()

    class GoodHandler:
        def run(self, intent):
            return ToolResult(output="A thorough, substantive answer about the topic.")

    registry = ToolRegistry()
    registry.register(Tool(name="good", route=Route.LOCAL_AI, handler=GoodHandler()))
    initial_trust = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)

    ExecutionEngine(registry=registry, router=router).execute(Route.LOCAL_AI, _intent())
    updated_trust = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)

    assert updated_trust > initial_trust


def test_stub_answer_lowers_trust_even_though_it_succeeds():
    """The honest half of the loop: the default local tier returns a stub, so
    'succeeding' with it still pulls the route's trust down."""
    router = Router()
    initial_trust = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)

    outcome = ExecutionEngine(router=router).execute(Route.LOCAL_AI, _intent())
    updated_trust = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)

    assert outcome.success is True
    assert outcome.quality <= 0.3  # a placeholder, not a real answer
    assert updated_trust < initial_trust


def test_execution_reports_failure_back_to_router():
    router = Router()

    class FailingHandler:
        def run(self, intent):
            return ToolResult(output="failed", success=False)

    registry = ToolRegistry()
    registry.register(Tool(name="flaky", route=Route.LOCAL_AI, handler=FailingHandler()))

    initial_trust = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)
    ExecutionEngine(registry=registry, router=router).execute(Route.LOCAL_AI, _intent())
    updated_trust = next(p.trust_score for p in router.profiles if p.route == Route.LOCAL_AI)

    assert updated_trust < initial_trust
