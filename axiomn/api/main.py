"""AXIOMN API: a single endpoint that runs the full Intent -> Route -> Execute pipeline."""
from fastapi import FastAPI
from pydantic import BaseModel

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
execution_engine = ExecutionEngine()


class IntentRequest(BaseModel):
    text: str


class IntentResponse(BaseModel):
    intent: str
    topic: str
    language: str
    difficulty: int
    confidence: float
    route: str
    result: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/intent", response_model=IntentResponse)
def handle_intent(payload: IntentRequest) -> IntentResponse:
    intent = intent_engine.classify(payload.text)
    route = router.route(intent)
    result = execution_engine.execute(route, intent)
    return IntentResponse(
        intent=intent.category.value,
        topic=intent.topic,
        language=intent.language,
        difficulty=intent.difficulty,
        confidence=intent.confidence,
        route=route.value,
        result=result,
    )
