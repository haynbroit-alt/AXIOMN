"""AXIOMN SDK: a thin client for the Intent Router API.

Deliberately has no dependency on the AXIOMN server package (no FastAPI, no
langdetect, no embedding model) — it only needs an HTTP endpoint speaking
the `/intent` contract. Point it at a local dev server, a hosted
deployment, or (for tests) an in-process ASGI app via a custom
`httpx.BaseTransport`.
"""
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class IntentResult:
    intent: str
    topic: str
    language: str
    difficulty: int
    confidence: float
    route: str
    tool: str
    result: str
    execution_time_ms: float

    @classmethod
    def from_dict(cls, data: dict) -> "IntentResult":
        return cls(
            intent=data["intent"],
            topic=data["topic"],
            language=data["language"],
            difficulty=data["difficulty"],
            confidence=data["confidence"],
            route=data["route"],
            tool=data["tool"],
            result=data["result"],
            execution_time_ms=data["execution_time_ms"],
        )


class AXIOMNClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def intent(self, text: str) -> IntentResult:
        response = self._client.post("/intent", json={"text": text})
        response.raise_for_status()
        return IntentResult.from_dict(response.json())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AXIOMNClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
