"""AXIOMN API: `POST /intent` runs the full Intent -> Route -> Execute -> Act
pipeline; `/queue/...` is the asynchronous half of the human route — where a
client polls for an escalated request's eventual answer, and where a human
operator finds and resolves pending tickets."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..action.engine import ActionEngine
from ..execution.engine import ExecutionEngine
from ..intent.engine import IntentEngine
from ..models.tools import default_registry
from ..queue.engine import (
    HumanQueue,
    Ticket,
    TicketAlreadyAnswered,
    TicketNotFound,
)
from ..router.router import Router

app = FastAPI(
    title="AXIOMN",
    description="An open-source intent mediation runtime.",
    version="0.1.0",
)

intent_engine = IntentEngine()
router = Router()
human_queue = HumanQueue()
execution_engine = ExecutionEngine(registry=default_registry(human_queue), router=router)
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
    action = action_engine.decide(intent, route, outcome.output, metadata=outcome.metadata)
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


class TicketAnswerRequest(BaseModel):
    text: str


class TicketResponse(BaseModel):
    ticket_id: str
    status: str
    question: str
    category: str
    language: str
    answer: str | None
    created_at: float
    answered_at: float | None


def _ticket_response(ticket: Ticket) -> TicketResponse:
    return TicketResponse(
        ticket_id=ticket.id,
        status=ticket.status.value,
        question=ticket.question,
        category=ticket.category,
        language=ticket.language,
        answer=ticket.answer,
        created_at=ticket.created_at,
        answered_at=ticket.answered_at,
    )


@app.get("/queue", response_model=list[TicketResponse])
def list_pending_tickets() -> list[TicketResponse]:
    """The human operator's worklist: every escalated request still waiting."""
    return [_ticket_response(t) for t in human_queue.pending()]


@app.get("/queue/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str) -> TicketResponse:
    """What clients poll after an `await_human` action, until `status == "answered"`."""
    try:
        return _ticket_response(human_queue.get(ticket_id))
    except TicketNotFound:
        raise HTTPException(status_code=404, detail=f"No ticket {ticket_id!r}") from None


@app.post("/queue/{ticket_id}/answer", response_model=TicketResponse)
def answer_ticket(ticket_id: str, payload: TicketAnswerRequest) -> TicketResponse:
    """The human side of the loop: an operator resolves a pending ticket."""
    try:
        return _ticket_response(human_queue.answer(ticket_id, payload.text))
    except TicketNotFound:
        raise HTTPException(status_code=404, detail=f"No ticket {ticket_id!r}") from None
    except TicketAlreadyAnswered:
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id!r} already answered") from None
