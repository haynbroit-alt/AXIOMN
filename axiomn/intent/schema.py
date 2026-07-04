from dataclasses import dataclass, field
from enum import Enum


class IntentCategory(str, Enum):
    LEARN = "learn"
    SOLVE = "solve"
    CREATE = "create"
    COMMUNICATE = "communicate"
    CONNECT = "connect"
    AUTOMATE = "automate"
    UNKNOWN = "unknown"


@dataclass
class IntentSignals:
    """Independent 0..1 scores for what a request demands (see
    `intent/signals.py`). Defaults are all zero, so an Intent built without
    analysis routes purely on `difficulty`, exactly as before signals existed."""

    reasoning: float = 0.0
    creativity: float = 0.0
    knowledge: float = 0.0
    stakes: float = 0.0

    @property
    def value(self) -> float:
        """Expected value of a strong answer, 0..1: the task's strongest
        cognitive demand, raised by how much a wrong answer would cost."""
        intelligence_need = max(self.reasoning, self.creativity, self.knowledge)
        return round(min(1.0, 0.55 * intelligence_need + 0.45 * self.stakes), 3)

    def as_dict(self) -> dict[str, float]:
        return {
            "reasoning": self.reasoning,
            "creativity": self.creativity,
            "knowledge": self.knowledge,
            "stakes": self.stakes,
            "value": self.value,
        }


@dataclass
class Intent:
    text: str
    category: IntentCategory
    topic: str
    language: str
    difficulty: int  # 1 (trivial) .. 10 (expert-only)
    confidence: float  # 0.0 .. 1.0
    ambiguity: float = 0.0  # 0.0 (crisp) .. 1.0 (top two categories are effectively tied)
    # How much intelligence the request *deserves*, scored independently of
    # difficulty (see intent/signals.py). Defaults to a zero-signal object, so
    # an Intent built without analysis routes on difficulty alone — unchanged.
    signals: IntentSignals = field(default_factory=IntentSignals)

    @property
    def value(self) -> float:
        """Expected value of a strong answer, 0..1 (from `signals`)."""
        return self.signals.value
