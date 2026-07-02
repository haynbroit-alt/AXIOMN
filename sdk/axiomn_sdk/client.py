"""AXIOMN SDK: a thin client for the Intent Router API.

Deliberately has no dependency on the AXIOMN server package (no FastAPI, no
langdetect, no embedding model) — it only needs an HTTP endpoint speaking
the versioned `/v1` contract. Point it at a local dev server, a hosted
deployment, or (for tests) an in-process ASGI app via a custom
`httpx.BaseTransport`.
"""
import time
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class Action:
    type: str
    payload: dict

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(type=data["type"], payload=data["payload"])


@dataclass
class IntentResult:
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
    action: Action
    model: Optional[str] = None  # which model the Gateway chose, when cloud-routed
    model_reason: Optional[str] = None  # and why

    @classmethod
    def from_dict(cls, data: dict) -> "IntentResult":
        return cls(
            intent=data["intent"],
            topic=data["topic"],
            language=data["language"],
            difficulty=data["difficulty"],
            confidence=data["confidence"],
            ambiguity=data["ambiguity"],
            route=data["route"],
            tool=data["tool"],
            result=data["result"],
            execution_time_ms=data["execution_time_ms"],
            action=Action.from_dict(data["action"]),
            model=data.get("model"),
            model_reason=data.get("model_reason"),
        )


@dataclass
class QueueTicket:
    """A human-escalated request. `answer` is None until a human resolves it."""

    ticket_id: str
    status: str  # "pending" | "answered"
    question: str
    category: str
    language: str
    answer: Optional[str]
    created_at: float
    answered_at: Optional[float]

    @classmethod
    def from_dict(cls, data: dict) -> "QueueTicket":
        return cls(
            ticket_id=data["ticket_id"],
            status=data["status"],
            question=data["question"],
            category=data["category"],
            language=data["language"],
            answer=data["answer"],
            created_at=data["created_at"],
            answered_at=data["answered_at"],
        )


class HumanAnswerTimeout(TimeoutError):
    """No human answered the ticket within the allotted wait."""


class AXIOMNClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def intent(self, text: str) -> IntentResult:
        response = self._client.post("/v1/intent", json={"text": text})
        response.raise_for_status()
        return IntentResult.from_dict(response.json())

    def queue_status(self, ticket_id: str) -> QueueTicket:
        response = self._client.get(f"/v1/queue/{ticket_id}")
        response.raise_for_status()
        return QueueTicket.from_dict(response.json())

    def answer_ticket(self, ticket_id: str, text: str) -> QueueTicket:
        """The operator side: resolve a pending human-queue ticket."""
        response = self._client.post(f"/v1/queue/{ticket_id}/answer", json={"text": text})
        response.raise_for_status()
        return QueueTicket.from_dict(response.json())

    def metrics(self) -> dict:
        """Aggregate runtime metrics: volume, latency, route shares, cost."""
        response = self._client.get("/v1/metrics")
        response.raise_for_status()
        return response.json()

    def wait_for_human(
        self, ticket_id: str, timeout: float = 60.0, poll_interval: float = 0.5
    ) -> QueueTicket:
        """Block until a human answers the ticket, polling `/queue/{id}`.

        Raises `HumanAnswerTimeout` if no answer arrives within `timeout`
        seconds. For non-blocking flows, poll `queue_status()` yourself.
        """
        deadline = time.monotonic() + timeout
        while True:
            ticket = self.queue_status(ticket_id)
            if ticket.status == "answered":
                return ticket
            if time.monotonic() >= deadline:
                raise HumanAnswerTimeout(
                    f"Ticket {ticket_id!r} still unanswered after {timeout}s"
                )
            time.sleep(poll_interval)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AXIOMNClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
