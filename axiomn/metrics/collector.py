"""Measurement instead of assumption: every request through the pipeline is
recorded here, and `snapshot()` is what `GET /metrics` serves.

The questions this exists to answer are the ones routing quality and cost
decisions depend on: how many requests, how fast (average and tail), what
share resolved locally vs. cloud vs. human, how often execution succeeded,
and what it all cost. Per-user satisfaction signals belong to a future
feedback endpoint; everything measurable server-side today is here.

In-memory and thread-safe, like the HumanQueue: a Prometheus/OpenMetrics
exporter is an infrastructure-roadmap step that would sit behind this same
`record()`/`snapshot()` contract.
"""
import threading
from collections import Counter, deque


def _percentile(sorted_values: list[float], fraction: float) -> float:
    index = round(fraction * (len(sorted_values) - 1))
    return sorted_values[index]


class MetricsCollector:
    def __init__(self, latency_window: int = 1000):
        self._lock = threading.Lock()
        self._total = 0
        self._successes = 0
        self._by_route: Counter[str] = Counter()
        self._by_category: Counter[str] = Counter()
        self._by_language: Counter[str] = Counter()
        # Tail latency is computed over a bounded recent window so memory
        # stays constant; totals and averages are all-time.
        self._recent_latencies: deque[float] = deque(maxlen=latency_window)
        self._latency_sum = 0.0
        self._cost_sum = 0.0

    def record(
        self,
        *,
        category: str,
        language: str,
        route: str,
        latency_ms: float,
        success: bool,
        cost: float = 0.0,
    ) -> None:
        with self._lock:
            self._total += 1
            self._successes += int(success)
            self._by_route[route] += 1
            self._by_category[category] += 1
            self._by_language[language] += 1
            self._recent_latencies.append(latency_ms)
            self._latency_sum += latency_ms
            self._cost_sum += cost

    def snapshot(self) -> dict:
        with self._lock:
            total = self._total
            if total == 0:
                return {"requests": {"total": 0}}
            recent = sorted(self._recent_latencies)
            return {
                "requests": {
                    "total": total,
                    "success_rate": round(self._successes / total, 4),
                },
                "routes": {
                    route: {"count": count, "share": round(count / total, 4)}
                    for route, count in sorted(self._by_route.items())
                },
                "latency_ms": {
                    "avg": round(self._latency_sum / total, 3),
                    "p50": round(_percentile(recent, 0.50), 3),
                    "p95": round(_percentile(recent, 0.95), 3),
                    "window": len(recent),
                },
                "cost": {
                    "total": round(self._cost_sum, 4),
                    "avg_per_request": round(self._cost_sum / total, 6),
                },
                "categories": dict(sorted(self._by_category.items())),
                "languages": dict(sorted(self._by_language.items())),
            }
