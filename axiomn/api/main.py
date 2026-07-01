"""AXIOMN API: a single endpoint that runs the full Intent -> Route -> Execute -> Act pipeline."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..action.engine import ActionEngine
from ..execution.engine import ExecutionEngine
from ..intent.engine import IntentEngine
from ..router.router import Router

app = FastAPI(
    title="AXIOMN",
    description="The universal intent mediation layer.",
    version="0.1.0",
)

intent_engine = IntentEngine()
router = Router()
execution_engine = ExecutionEngine(router=router)
action_engine = ActionEngine()

_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")


class IntentRequest(BaseModel):
    text: str


class ActionResponse(BaseModel):
    type: str
    payload: dict


class IntentResponse(BaseModel):
    intent: str
    topic: str
    language: str
    difficulty: int
    confidence: float
    ambiguity: float
    route: str
    tool: str
    result: str
    execution_time_ms: float
    action: ActionResponse


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/intent", response_model=IntentResponse)
def handle_intent(payload: IntentRequest) -> IntentResponse:
    intent = intent_engine.classify(payload.text)
    route = router.route(intent)
    outcome = execution_engine.execute(route, intent)
    action = action_engine.decide(intent, route, outcome.output)
    return IntentResponse(
        intent=intent.category.value,
        topic=intent.topic,
        language=intent.language,
        difficulty=intent.difficulty,
        confidence=intent.confidence,
        ambiguity=intent.ambiguity,
        route=route.value,
        tool=outcome.tool_name,
        result=outcome.output,
        execution_time_ms=round(outcome.latency_ms, 2),
        action=ActionResponse(type=action.type.value, payload=action.payload),
    )
