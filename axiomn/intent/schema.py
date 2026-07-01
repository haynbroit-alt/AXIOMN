from dataclasses import dataclass
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
class Intent:
    text: str
    category: IntentCategory
    topic: str
    language: str
    difficulty: int  # 1 (trivial) .. 10 (expert-only)
    confidence: float  # 0.0 .. 1.0
    ambiguity: float = 0.0  # 0.0 (crisp) .. 1.0 (top two categories are effectively tied)
