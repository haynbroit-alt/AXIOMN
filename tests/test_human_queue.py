import pytest

from axiomn.intent.schema import Intent, IntentCategory
from axiomn.models.tools import HumanQueueHandler
from axiomn.queue.engine import (
    HumanQueue,
    TicketAlreadyAnswered,
    TicketNotFound,
    TicketStatus,
)


def _intent(text: str = "Find me a tax law expert") -> Intent:
    return Intent(
        text=text,
        category=IntentCategory.CONNECT,
        topic=text,
        language="en",
        difficulty=3,
        confidence=0.8,
    )


def test_enqueue_creates_pending_ticket_with_unique_id():
    queue = HumanQueue()
    first = queue.enqueue(_intent())
    second = queue.enqueue(_intent())

    assert first.status is TicketStatus.PENDING
    assert first.question == "Find me a tax law expert"
    assert first.answer is None
    assert first.id != second.id


def test_answer_resolves_the_ticket():
    queue = HumanQueue()
    ticket = queue.enqueue(_intent())

    answered = queue.answer(ticket.id, "Try Maître Dupont, she specializes in this.")

    assert answered.status is TicketStatus.ANSWERED
    assert answered.answer == "Try Maître Dupont, she specializes in this."
    assert answered.answered_at is not None
    # And the stored ticket reflects it — answer() is not a copy.
    assert queue.get(ticket.id).status is TicketStatus.ANSWERED


def test_get_unknown_ticket_raises():
    with pytest.raises(TicketNotFound):
        HumanQueue().get("nope")


def test_answer_unknown_ticket_raises():
    with pytest.raises(TicketNotFound):
        HumanQueue().answer("nope", "hello")


def test_answer_is_immutable_once_given():
    queue = HumanQueue()
    ticket = queue.enqueue(_intent())
    queue.answer(ticket.id, "first answer")

    with pytest.raises(TicketAlreadyAnswered):
        queue.answer(ticket.id, "second answer")
    assert queue.get(ticket.id).answer == "first answer"


def test_pending_lists_only_unanswered_tickets():
    queue = HumanQueue()
    open_ticket = queue.enqueue(_intent("still waiting"))
    done_ticket = queue.enqueue(_intent("already handled"))
    queue.answer(done_ticket.id, "done")

    pending_ids = [t.id for t in queue.pending()]
    assert pending_ids == [open_ticket.id]


def test_handler_enqueues_a_real_ticket_and_exposes_its_id():
    queue = HumanQueue()
    result = HumanQueueHandler(queue=queue).run(_intent())

    ticket_id = result.metadata["ticket_id"]
    assert queue.get(ticket_id).status is TicketStatus.PENDING
    assert "Queued" in result.output
