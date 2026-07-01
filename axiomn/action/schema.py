from dataclasses import dataclass, field
from enum import Enum


class ActionType(str, Enum):
    VOICE_REPLY = "voice_reply"  # speak/display the result now
    COPY_TO_CLIPBOARD = "copy_to_clipboard"  # generated content the user likely wants to paste
    OPEN_URL = "open_url"  # hand off to an external resource
    SCHEDULE_TASK = "schedule_task"  # the request describes a recurring/future action
    AWAIT_HUMAN = "await_human"  # queued for a person; there is no answer yet


@dataclass
class Action:
    type: ActionType
    payload: dict = field(default_factory=dict)
