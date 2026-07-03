"""The savings-estimate arithmetic — AXIOMN's "see the receipts on your own
traffic" value prop, made trivially auditable. Pure and offline: no model calls,
no API keys, no classification (the endpoint that feeds real routes is covered
in the API tests).
"""
from axiomn.gateway.estimate import EstimateRow, estimate_savings


def test_savings_are_computed_against_the_flagship_baseline():
    # Two cheap local routes + one flagship-priced route, baseline = all flagship.
    rows = [
        EstimateRow(route="local_ai", cost=0.0, baseline_cost=0.03),
        EstimateRow(route="local_ai", cost=0.0, baseline_cost=0.03),
        EstimateRow(route="cloud_ai", cost=0.03, baseline_cost=0.03),
    ]
    est = estimate_savings(rows)
    assert est.requests == 3
    assert est.projected_cost == 0.03
    assert est.baseline_cost == 0.09
    assert est.saved == 0.06
    assert round(est.savings_rate, 4) == round(0.06 / 0.09, 4)
    assert est.by_route == {"local_ai": 2, "cloud_ai": 1}


def test_empty_batch_is_zero_not_nan():
    est = estimate_savings([])
    assert est.requests == 0
    assert est.savings_rate == 0.0
    assert est.saved == 0.0


def test_zero_baseline_does_not_divide_by_zero():
    est = estimate_savings([EstimateRow(route="local_ai", cost=0.0, baseline_cost=0.0)])
    assert est.savings_rate == 0.0


def test_no_savings_when_everything_routes_to_flagship():
    rows = [EstimateRow(route="cloud_ai", cost=0.03, baseline_cost=0.03) for _ in range(5)]
    est = estimate_savings(rows)
    assert est.saved == 0.0
    assert est.savings_rate == 0.0


def test_to_dict_is_rounded_and_serializable():
    est = estimate_savings([EstimateRow(route="local_ai", cost=0.0, baseline_cost=0.03)])
    d = est.to_dict()
    assert d["saved"] == 0.03
    assert d["by_route"] == {"local_ai": 1}
