from axiomn.action.engine import ActionEngine
from axiomn.action.schema import ActionType
from axiomn.intent.schema import Intent, IntentCategory
from axiomn.router.router import Route


def _intent(category: IntentCategory) -> Intent:
    return Intent(text="x", category=category, topic="black holes", language="en", difficulty=1, confidence=0.8)


def test_human_queue_route_always_yields_await_human_regardless_of_category():
    # Even a LEARN request should surface as "still working on it" once a
    # human is involved — the route determines this, not the category.
    action = ActionEngine().decide(_intent(IntentCategory.LEARN), Route.HUMAN_QUEUE, "Queued for a human/expert")
    assert action.type == ActionType.AWAIT_HUMAN
    assert action.payload["message"] == "Queued for a human/expert"


def test_learn_intent_on_local_ai_yields_voice_reply():
    action = ActionEngine().decide(_intent(IntentCategory.LEARN), Route.LOCAL_AI, "some answer")
    assert action.type == ActionType.VOICE_REPLY
    assert action.payload["text"] == "some answer"


def test_create_intent_yields_copy_to_clipboard():
    action = ActionEngine().decide(_intent(IntentCategory.CREATE), Route.CLOUD_AI, "a poem")
    assert action.type == ActionType.COPY_TO_CLIPBOARD


def test_automate_intent_yields_schedule_task():
    action = ActionEngine().decide(_intent(IntentCategory.AUTOMATE), Route.CLOUD_AI, "scheduled")
    assert action.type == ActionType.SCHEDULE_TASK


def test_connect_intent_yields_open_url_with_encoded_topic():
    action = ActionEngine().decide(_intent(IntentCategory.CONNECT), Route.CLOUD_AI, "connecting")
    assert action.type == ActionType.OPEN_URL
    assert action.payload["url"] == "https://www.google.com/search?q=black%20holes"
