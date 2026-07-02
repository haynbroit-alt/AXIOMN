"""The Human Queue: the delivery mechanism that makes `await_human` honest.

Escalating to a human is inherently asynchronous — the answer does not
exist when the HTTP request returns. Until now the pipeline could only
*signal* that (`ActionType.AWAIT_HUMAN`); the escalated request itself
went nowhere, and no answer could ever come back. Here, every escalated
request becomes a `Ticket` with an id: a human answers it out-of-band
(`answer()`), and the client retrieves the result by polling the ticket
(`get()`).

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


class HumanQueue:
    """Thread-safe in-memory ticket store for human-escalated intents."""

    def __init__(self):
        self._tickets: dict[str, Ticket] = {}
        self._lock = threading.Lock()

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

    def get(self, ticket_id: str) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise TicketNotFound(ticket_id)
        return ticket

    def answer(self, ticket_id: str, text: str) -> Ticket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFound(ticket_id)
            if ticket.status is TicketStatus.ANSWERED:
                raise TicketAlreadyAnswered(ticket_id)
            ticket.answer = text
            ticket.status = TicketStatus.ANSWERED
            ticket.answered_at = time.time()
            return ticket

    def pending(self) -> list[Ticket]:
        with self._lock:
            return [t for t in self._tickets.values() if t.status is TicketStatus.PENDING]
