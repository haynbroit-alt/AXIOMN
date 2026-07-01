"""AXIOMN API: a single endpoint that runs the full Intent -> Route -> Execute -> Act pipeline."""
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..action.engine import ActionEngine
from ..execution.engine import ExecutionEngine
from ..intent.engine import IntentEngine
from ..router.router import Router
from .security import RateLimiter, require_api_key

app = FastAPI(
    title="AXIOMN",
    description="The universal intent mediation layer.",
    version="0.1.0",
)

intent_engine = IntentEngine()
router = Router(persistence_path=os.environ.get("AXIOMN_ROUTER_STATE_PATH"))
execution_engine = ExecutionEngine(router=router)
action_engine = ActionEngine()
rate_limiter = RateLimiter(max_requests=int(os.environ.get("AXIOMN_RATE_LIMIT_PER_MINUTE", "60")))

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


def _client_id(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    if x_api_key:
        return x_api_key
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(client_id: str = Depends(_client_id)) -> None:
    rate_limiter.check(client_id)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/intent",
    response_model=IntentResponse,
    dependencies=[Depends(require_api_key), Depends(_enforce_rate_limit)],
)
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
