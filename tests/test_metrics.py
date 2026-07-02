from axiomn.metrics.collector import MetricsCollector


def _record(collector: MetricsCollector, route: str = "local_ai", **overrides) -> None:
    defaults = dict(
        category="learn",
        language="en",
        route=route,
        latency_ms=10.0,
        success=True,
        cost=0.0,
    )
    defaults.update(overrides)
    collector.record(**defaults)


def test_empty_collector_reports_zero_requests():
    assert MetricsCollector().snapshot() == {"requests": {"total": 0}}


def test_counts_route_shares_and_success_rate():
    collector = MetricsCollector()
    _record(collector, route="local_ai")
    _record(collector, route="local_ai")
    _record(collector, route="cloud_ai", success=False)
    _record(collector, route="human_queue")

    snap = collector.snapshot()
    assert snap["requests"]["total"] == 4
    assert snap["requests"]["success_rate"] == 0.75
    assert snap["routes"]["local_ai"] == {"count": 2, "share": 0.5}
    assert snap["routes"]["cloud_ai"]["share"] == 0.25
    assert snap["routes"]["human_queue"]["share"] == 0.25


def test_latency_average_and_percentiles():
    collector = MetricsCollector()
    for latency in [10.0, 20.0, 30.0, 40.0, 100.0]:
        _record(collector, latency_ms=latency)

    latency = collector.snapshot()["latency_ms"]
    assert latency["avg"] == 40.0
    assert latency["p50"] == 30.0
    assert latency["p95"] == 100.0
    assert latency["window"] == 5


def test_cost_accumulates_and_averages():
    collector = MetricsCollector()
    _record(collector, cost=0.0)
    _record(collector, cost=0.02)

    cost = collector.snapshot()["cost"]
    assert cost["total"] == 0.02
    assert cost["avg_per_request"] == 0.01


def test_latency_window_is_bounded():
    collector = MetricsCollector(latency_window=3)
    for latency in [1.0, 2.0, 3.0, 4.0]:
        _record(collector, latency_ms=latency)

    snap = collector.snapshot()
    # The percentile window forgot the first sample; the all-time avg didn't.
    assert snap["latency_ms"]["window"] == 3
    assert snap["latency_ms"]["p50"] == 3.0
    assert snap["latency_ms"]["avg"] == 2.5


def test_categories_and_languages_are_counted():
    collector = MetricsCollector()
    _record(collector, category="learn", language="fr")
    _record(collector, category="solve", language="fr")

    snap = collector.snapshot()
    assert snap["categories"] == {"learn": 1, "solve": 1}
    assert snap["languages"] == {"fr": 2}
