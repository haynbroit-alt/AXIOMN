"""The Router: decides which backend should resolve a given Intent."""
from dataclasses import dataclass
from enum import Enum

from ..intent.schema import Intent, IntentCategory


class Route(str, Enum):
    LOCAL_AI = "local_ai"
    CLOUD_AI = "cloud_ai"
    HUMAN_QUEUE = "human_queue"


@dataclass
class RoutingThresholds:
    local_max: int = 3
    cloud_max: int = 7


class Router:
    def __init__(self, thresholds: RoutingThresholds | None = None):
        self.thresholds = thresholds or RoutingThresholds()

    def route(self, intent: Intent) -> Route:
        if intent.category == IntentCategory.CONNECT:
            return Route.HUMAN_QUEUE
        if intent.difficulty <= self.thresholds.local_max:
            return Route.LOCAL_AI
        if intent.difficulty <= self.thresholds.cloud_max:
            return Route.CLOUD_AI
        return Route.HUMAN_QUEUE
