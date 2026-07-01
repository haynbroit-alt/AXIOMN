"""The Action Engine: the last step of the pipeline, after execution.

A raw text `result` isn't enough for a real client (a mobile app, a
browser extension) to act on — it also needs to know *what kind of thing*
to do with that result: speak it immediately, copy it, open a link,
schedule something for later, or — critically — wait, because a human is
involved and there is no answer yet. That last case matters: escalating
to `human_queue` is asynchronous, and a client that doesn't know that will
render a queued request identically to an instant one and confuse the
user with silence. `Action.type == AWAIT_HUMAN` is the signal a client
needs to show "still working on it" instead.
"""
from urllib.parse import quote

from ..intent.schema import Intent, IntentCategory
from ..router.router import Route
from .schema import Action, ActionType

_CATEGORY_ACTIONS: dict[IntentCategory, ActionType] = {
    IntentCategory.LEARN: ActionType.VOICE_REPLY,
    IntentCategory.SOLVE: ActionType.VOICE_REPLY,
    IntentCategory.COMMUNICATE: ActionType.VOICE_REPLY,
    IntentCategory.CREATE: ActionType.COPY_TO_CLIPBOARD,
    IntentCategory.AUTOMATE: ActionType.SCHEDULE_TASK,
    IntentCategory.CONNECT: ActionType.OPEN_URL,
    IntentCategory.UNKNOWN: ActionType.VOICE_REPLY,
}


class ActionEngine:
    def decide(self, intent: Intent, route: Route, result_text: str) -> Action:
        if route == Route.HUMAN_QUEUE:
            return Action(type=ActionType.AWAIT_HUMAN, payload={"message": result_text})

        action_type = _CATEGORY_ACTIONS.get(intent.category, ActionType.VOICE_REPLY)
        payload = {"text": result_text}
        if action_type == ActionType.OPEN_URL:
            payload["url"] = f"https://www.google.com/search?q={quote(intent.topic)}"
        return Action(type=action_type, payload=payload)
