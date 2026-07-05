"""The Human Queue: the delivery mechanism that makes `await_human` honest.

Escalating to a human is inherently asynchronous — the answer does not
exist when the HTTP request returns. Until now the pipeline could only
*signal* that (`ActionType.AWAIT_HUMAN`); the escalated request itself
went nowhere, and no answer could ever come back. Here, every escalated
request becomes a `Ticket` with an id: a human answers it out-of-band
(`answer()`), and the client retrieves the result by polling the ticket
(`get()`).

A ticket nobody answers is still a broken promise — "every question
should have an answer" doesn't stop being true just because no operator
is staffing the queue. So a ticket carries a `ttl_seconds` and, once a
client polls (or an operator looks) past that deadline, it auto-resolves
into a clear timeout answer instead of staying `pending` forever.

In-memory and thread-safe. Durable storage and operator authentication
belong to the infrastructure roadmap; the contract here
(enqueue / get / answer / pending) is what a persistent implementation
will honor.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from ..intent.schema import Intent

# How long a ticket may sit unanswered before it auto-resolves with a
# timeout message. None disables expiry (a ticket can wait forever) —
# useful for tests and for deployments with a reliably staffed queue.
DEFAULT_TTL_SECONDS = 300.0


class TicketStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"


class TicketNotFound(KeyError):
    """No ticket exists with the given id."""


class TicketAlreadyAnswered(ValueError):
    """The ticket was already resolved; an answer is immutable once given."""


@dataclass
class Ticket:
    id: str
    question: str
    category: str
    language: str
    status: TicketStatus = TicketStatus.PENDING
    answer: str | None = None
    created_at: float = field(default_factory=time.time)
    answered_at: float | None = None
    timed_out: bool = False


def _timeout_answer(ttl_seconds: float) -> str:
    return (
        "No human operator answered this request within the expected wait "
        f"time ({int(ttl_seconds)}s). Escalation timed out — please retry "
        "or rephrase your request so it can be resolved automatically."
    )


class HumanQueue:
    """Thread-safe in-memory ticket store for human-escalated intents."""

    def __init__(self, ttl_seconds: float | None = DEFAULT_TTL_SECONDS):
        self._tickets: dict[str, Ticket] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def enqueue(self, intent: Intent) -> Ticket:
        ticket = Ticket(
            id=uuid.uuid4().hex,
            question=intent.text,
            category=intent.category.value,
            language=intent.language,
        )
        with self._lock:
            self._tickets[ticket.id] = ticket
        return ticket

    def _expire_locked(self, ticket: Ticket) -> None:
        """Auto-resolve a ticket that's been pending past its TTL.

        Called with `_lock` held. A client polling a stale ticket, or an
        operator listing pending work, is what actually triggers the
        expiry — there's no background thread, so this stays simple and
        deterministic to test.
        """
        if self._ttl_seconds is None or ticket.status is not TicketStatus.PENDING:
            return
        if time.time() - ticket.created_at < self._ttl_seconds:
            return
        ticket.answer = _timeout_answer(self._ttl_seconds)
        ticket.status = TicketStatus.ANSWERED
        ticket.answered_at = time.time()
        ticket.timed_out = True

    def get(self, ticket_id: str) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFound(ticket_id)
            self._expire_locked(ticket)
            return ticket

    def answer(self, ticket_id: str, text: str) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFound(ticket_id)
            self._expire_locked(ticket)
            if ticket.status is TicketStatus.ANSWERED:
                raise TicketAlreadyAnswered(ticket_id)
            ticket.answer = text
            ticket.status = TicketStatus.ANSWERED
            ticket.answered_at = time.time()
            return ticket

    def pending(self) -> list[Ticket]:
        with self._lock:
            for ticket in self._tickets.values():
                self._expire_locked(ticket)
            return [t for t in self._tickets.values() if t.status is TicketStatus.PENDING]
