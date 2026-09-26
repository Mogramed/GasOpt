"""Frozen TEST evaluation. This module has no optimizer imports."""
from gasopt.baselines import immediate_schedule
from gasopt.evaluation.out_of_sample import evaluate_schedules
from gasopt.api.serialization import cost_points, records

def evaluate_frozen(transactions, test, schedule, alpha, exploratory):
    frozen = dict(schedule)
    daily, table = evaluate_schedules(transactions, test,
        {"immediate": immediate_schedule(transactions), "selected": frozen}, alpha)
    row = table.set_index("strategy").loc["selected"].to_dict()
    return {"context": "TEST evaluation only", "alpha": alpha, "exploratory": exploratory,
            "schedule": frozen, "metrics": row,
            "daily_costs": records(daily.reset_index()),
            "sorted_costs": cost_points(daily.selected.to_dict(), alpha),
            "warning": f"TEST is evaluation-only. CVaR tail: {(1-alpha)*len(test):.2f} scenario equivalents. "
                       "No TEST-based lambda selection or statistical-significance claim."}
