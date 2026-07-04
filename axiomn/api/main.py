"""AXIOMN API. `POST /v1/intent` runs the full Intent -> Route -> Execute -> Act
pipeline; `/v1/queue/...` is the asynchronous half of the human route — where a
client polls for an escalated request's eventual answer, and where a human
operator finds and resolves pending tickets; `GET /v1/metrics` reports what the
runtime actually did (volume, latency, route shares, success rate, cost).

`/v1` is the versioned, stable contract — the one `/docs` documents and the
SDK targets. The same endpoints also answer on unversioned paths (`/intent`,
`/queue/...`) as compatibility aliases for pre-v1 clients and for the
kernel-emitted `status_url` pointer; they are hidden from the schema.
"""
import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ..audit import build_audit_sink, build_event
from ..gateway.estimate import EstimateRow, estimate_savings
from ..observability import configure_logging, logger, request_id_var

from ..action.engine import ActionEngine
from ..execution.engine import ExecutionEngine
from ..gateway.handler import build_default_gateway
from ..intent.engine import IntentEngine
from ..intent.llm_fallback import build_default_fallback_classifier
from ..metrics.collector import MetricsCollector
from ..models.tools import default_registry
from ..sandbox import build_verity_handler
from ..queue.engine import (
    HumanQueue,
    Ticket,
    TicketAlreadyAnswered,
    TicketNotFound,
)
from ..router.router import Route, Router
from .security import RateLimiter, require_api_key

configure_logging()

app = FastAPI(
    title="AXIOMN",
    description="An open-source intent mediation runtime.",
    version="0.2.1",
)

router = Router(persistence_path=os.environ.get("AXIOMN_ROUTER_STATE_PATH"))
human_queue = HumanQueue()
gateway = build_default_gateway()
# When the keyword heuristic can't read a request (UNKNOWN / near-tie), a
# cheap Gateway model classifies it by meaning instead of dead-ending it.
# Fail-open: without provider keys the fallback resolves to the heuristic's
# own result, so local/dev behavior is unchanged. AXIOMN_LLM_CLASSIFIER=0
# disables the LLM call entirely.
if os.environ.get("AXIOMN_LLM_CLASSIFIER", "1").lower() in ("0", "false"):
    intent_engine = IntentEngine()
else:
    intent_engine = IntentEngine(
        classifier=build_default_fallback_classifier(gateway.catalog, gateway.clients)
    )
# The savings estimator uses a keyword-only engine on purpose: /v1/estimate is a
# dry run that must stay fast, deterministic, and genuinely model-free (no LLM
# fallback calls, so its "no model calls, zero API keys" promise holds even in
# real mode). An estimate can be approximate; it must not be slow or billable.
estimate_intent_engine = IntentEngine()
# Opt-in: with AXIOMN_VERITY_URL set, code-execution (AUTOMATE) intents run in
# VERITY's isolated sandbox and come back with an Ed25519 proof instead of a
# local heuristic answer. Unset -> None -> the sandbox tool is not registered
# and the runtime behaves exactly as before.
sandbox_handler = build_verity_handler()
execution_engine = ExecutionEngine(
    registry=default_registry(
        human_queue, cloud_handler=gateway, sandbox_handler=sandbox_handler
    ),
    router=router,
)
action_engine = ActionEngine()
metrics = MetricsCollector()
# The AXIOMN -> SIOS edge: every decision is emitted as a SHA-256-hashed audit
# event. Log-only by default; also POSTs to a SIOS ingest endpoint when
# AXIOMN_AUDIT_URL is set (fail-open — the auditor being down never breaks a
# request). See axiomn/audit.py.
audit_sink = build_audit_sink()
rate_limiter = RateLimiter(max_requests=int(os.environ.get("AXIOMN_RATE_LIMIT_PER_MINUTE", "60")))


def _client_id(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    # The API key doubles as the rate-limit bucket; anonymous clients are
    # bucketed by IP.
    if x_api_key:
        return x_api_key
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(client_id: str = Depends(_client_id)) -> None:
    rate_limiter.check(client_id)

# The embeddable widget (/ui/widget.js) runs on third-party origins — the
# browser needs CORS consent to let those pages call the API. Access is
# controlled by API keys (AXIOMN_API_KEYS), not by origin; deployments that
# want origin pinning can set AXIOMN_CORS_ORIGINS to a comma-separated list.
_cors_origins = [
    o.strip() for o in os.environ.get("AXIOMN_CORS_ORIGINS", "*").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_context(request: Request, call_next):
    """Tag every request with an id and emit one structured access log line.

    The id is taken from an inbound ``X-Request-ID`` when present (so it can be
    threaded through from an upstream proxy) or minted here, exposed back in the
    response header, and bound into the log context so decision logs emitted
    while serving carry the same id.
    """
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
    except Exception:
        logger.exception(
            "request.error",
            extra={"method": request.method, "path": request.url.path},
        )
        raise
    finally:
        request_id_var.reset(token)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = rid
    logger.info(
        "request.handled",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
        },
    )
    return response


_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")


def _cost_of(route: Route) -> float:
    return next((p.cost_per_call for p in router.profiles if p.route == route), 0.0)


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
    model: str | None = None  # which model the Gateway chose, when cloud-routed
    model_reason: str | None = None  # and why — the choice is always explainable
    result: str
    execution_time_ms: float
    action: ActionResponse


api = APIRouter()


@api.get("/health")
def health() -> dict:
    """Health plus deploy observability: which build is actually serving.

    Debugging 'did the redeploy take?' from the outside is guesswork
    without this — the page and schema look identical across builds.
    `build` is the container image reference when the platform provides
    one (e.g. Fly.io's FLY_IMAGE_REF), absent otherwise.
    """
    payload = {
        "status": "ok",
        "version": app.version,
        # Ops-visible honesty signal: 'simulated'/'mixed' means some answers are
        # placeholders, not real model output. Lets a monitor catch a deploy
        # that came up without provider keys instead of discovering it in a
        # user-facing `[simulated:...]` answer.
        "provider_mode": gateway.provider_mode(),
    }
    image_ref = os.environ.get("FLY_IMAGE_REF")
    if image_ref:
        payload["build"] = image_ref
    return payload


@api.post(
    "/intent",
    response_model=IntentResponse,
    dependencies=[Depends(require_api_key), Depends(_enforce_rate_limit)],
)
def handle_intent(payload: IntentRequest) -> IntentResponse:
    intent = intent_engine.classify(payload.text)
    route = router.route(intent)
    outcome = execution_engine.execute(route, intent)
    action = action_engine.decide(intent, route, outcome.output, metadata=outcome.metadata)
    cost = outcome.metadata.get("cost", _cost_of(route))
    if route == Route.HUMAN_QUEUE:
        # A human isn't replaceable by the flagship model — no savings claim.
        baseline_cost = cost
    else:
        # What this request would have cost with no routing: everything to
        # the Gateway's flagship model. That's the measured-savings baseline.
        baseline_cost = outcome.metadata.get(
            "baseline_cost", gateway.catalog.flagship().cost_per_call
        )
    metrics.record(
        category=intent.category.value,
        language=intent.language,
        route=route.value,
        latency_ms=outcome.latency_ms,
        success=outcome.success,
        cost=cost,
        baseline_cost=baseline_cost,
        model=outcome.metadata.get("model"),
    )
    # The decision as a tamper-evident, auditable record — the AXIOMN -> SIOS
    # edge. The user's text is hashed, never stored (RGPD); the event carries
    # the decision, its cost baseline, and any VERITY proof, plus a SHA-256
    # content hash SIOS can verify independently.
    audit_sink.emit(
        build_event(
            payload_text=payload.text,
            category=intent.category.value,
            language=intent.language,
            route=route.value,
            tool=outcome.tool_name,
            success=outcome.success,
            cost=cost,
            baseline_cost=baseline_cost,
            latency_ms=outcome.latency_ms,
            model=outcome.metadata.get("model"),
            model_reason=outcome.metadata.get("selection_reason"),
            proof=outcome.metadata.get("verity"),
        )
    )
    return IntentResponse(
        intent=intent.category.value,
        topic=intent.topic,
        language=intent.language,
        difficulty=intent.difficulty,
        confidence=intent.confidence,
        ambiguity=intent.ambiguity,
        route=route.value,
        tool=outcome.tool_name,
        model=outcome.metadata.get("model"),
        model_reason=outcome.metadata.get("selection_reason"),
        result=outcome.output,
        execution_time_ms=round(outcome.latency_ms, 2),
        action=ActionResponse(type=action.type.value, payload=action.payload),
    )


class EstimateRequest(BaseModel):
    # Bounded so an unauthenticated caller can't force unbounded classification
    # work in one request: at most 100 prompts, each at most 4000 chars. Larger
    # corpora are estimated by paging through several calls (which the rate
    # limiter then throttles).
    texts: Annotated[
        list[Annotated[str, StringConstraints(max_length=4000)]],
        Field(min_length=1, max_length=100),
    ]


class EstimateItem(BaseModel):
    text: str
    route: str
    cost: float
    baseline_cost: float


class EstimateResponse(BaseModel):
    summary: dict
    items: list[EstimateItem]


@api.post(
    "/estimate",
    response_model=EstimateResponse,
    dependencies=[Depends(_enforce_rate_limit)],
)
def estimate(payload: EstimateRequest) -> EstimateResponse:
    """Dry-run savings on your own traffic — no execution, no provider keys.

    Give a batch of representative prompts; AXIOMN classifies and routes each
    (the exact decision it would make live) and prices it against the no-routing
    baseline (everything to the flagship model). Returns the per-request routes
    and an aggregate projected-vs-baseline savings report — computed from your
    traffic, not a marketing figure. Nothing is executed and no model is called,
    so it works with zero API keys configured.
    """
    flagship_cost = gateway.catalog.flagship().cost_per_call
    rows: list[EstimateRow] = []
    items: list[EstimateItem] = []
    for text in payload.texts:
        intent = estimate_intent_engine.classify(text)
        route = router.route(intent)
        # Mirror the live /v1/intent cost model exactly, as a dry run:
        #  - cloud: the model the Gateway would pick, priced from the catalog;
        #  - human: no savings claim — a human isn't a cheaper flagship, so its
        #    baseline is its own cost (contributes 0 to savings), never a
        #    spurious "negative saving";
        #  - local: free, still measured against the flagship baseline.
        if route == Route.CLOUD_AI:
            profile, _ = gateway.catalog.select(intent)
            cost, baseline = profile.cost_per_call, flagship_cost
        elif route == Route.HUMAN_QUEUE:
            cost = baseline = _cost_of(route)
        else:
            cost, baseline = _cost_of(route), flagship_cost
        rows.append(EstimateRow(route=route.value, cost=cost, baseline_cost=baseline))
        items.append(
            EstimateItem(text=text, route=route.value, cost=cost, baseline_cost=baseline)
        )
    return EstimateResponse(summary=estimate_savings(rows).to_dict(), items=items)


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


@api.get("/queue", response_model=list[TicketResponse])
def list_pending_tickets() -> list[TicketResponse]:
    """The human operator's worklist: every escalated request still waiting."""
    return [_ticket_response(t) for t in human_queue.pending()]


@api.get("/queue/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str) -> TicketResponse:
    """What clients poll after an `await_human` action, until `status == "answered"`."""
    try:
        return _ticket_response(human_queue.get(ticket_id))
    except TicketNotFound:
        raise HTTPException(status_code=404, detail=f"No ticket {ticket_id!r}") from None


@api.post(
    "/queue/{ticket_id}/answer",
    response_model=TicketResponse,
    dependencies=[Depends(require_api_key)],
)
def answer_ticket(ticket_id: str, payload: TicketAnswerRequest) -> TicketResponse:
    """The human side of the loop: an operator resolves a pending ticket."""
    try:
        return _ticket_response(human_queue.answer(ticket_id, payload.text))
    except TicketNotFound:
        raise HTTPException(status_code=404, detail=f"No ticket {ticket_id!r}") from None
    except TicketAlreadyAnswered:
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id!r} already answered") from None


@api.get("/metrics")
def get_metrics() -> dict:
    """What the runtime actually did — decisions rest on data, not assumption."""
    return metrics.snapshot()


# The versioned contract clients should target, and the only one /docs shows.
app.include_router(api, prefix="/v1")
# Unversioned compatibility aliases (pre-v1 clients, kernel-emitted status_url).
app.include_router(api, include_in_schema=False)
