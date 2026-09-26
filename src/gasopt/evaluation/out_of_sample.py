"""Evaluate frozen schedules on held-out days, without access to an optimizer."""

from collections.abc import Mapping, Sequence
import numpy as np
import pandas as pd

from gasopt.evaluation.metrics import scenario_costs_eth, weighted_var_cvar
from gasopt.types import Scenario, Transaction


def cost_summary(costs: Sequence[float], alpha: float) -> dict[str, float]:
    """Descriptive distribution metrics; std uses ddof=0, p95 the inverse ECDF.

    VaR uses the configured alpha; p95 always means 95%. When alpha=.95 these
    agree. CVaR includes fractional mass at the tail boundary, without smoothing.
    """
    values = np.asarray(costs, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Costs must be a nonempty finite nonnegative vector.")
    var, cvar = weighted_var_cvar(values, np.full(len(values), 1 / len(values)), alpha)
    return {"mean_cost_eth": float(values.mean()), "median_cost_eth": float(np.median(values)),
            "std_cost_eth": float(values.std(ddof=0)),
            "p95_cost_eth": float(np.quantile(values, .95, method="inverted_cdf")),
            "var_eth": var, "cvar_eth": cvar, "max_cost_eth": float(values.max()),
            "min_cost_eth": float(values.min()), "tail_scenario_count": (1 - alpha) * len(values)}


def savings(immediate_mean: float, strategy_mean: float) -> dict[str, float]:
    """Principal savings use the ratio of mean costs, not mean daily percentages."""
    if not np.isfinite([immediate_mean, strategy_mean]).all() or immediate_mean <= 0 or strategy_mean < 0:
        raise ValueError("Savings require a positive baseline and nonnegative strategy mean.")
    absolute = immediate_mean - strategy_mean
    return {"savings_eth": absolute, "savings_fraction": absolute / immediate_mean,
            "savings_percent": 100 * absolute / immediate_mean}


def evaluate_schedules(
    transactions: Sequence[Transaction], test_scenarios: Sequence[Scenario],
    schedules: Mapping[str, Mapping[str, int]], alpha: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return TEST-only daily costs and summary metrics; never re-optimize."""
    if "immediate" not in schedules:
        raise ValueError("An immediate schedule is required for savings comparisons.")
    if not test_scenarios:
        raise ValueError("At least one TEST scenario is required.")
    if any(not np.isclose(s.probability, 1 / len(test_scenarios), atol=1e-12, rtol=0) for s in test_scenarios):
        raise ValueError("Daily TEST evaluation expects equiprobable calendar days.")
    costs = pd.DataFrame({name: scenario_costs_eth(transactions, test_scenarios, schedule)
                          for name, schedule in schedules.items()})
    costs.index.name = "test_day"
    baseline_mean = float(costs.immediate.mean())
    rows = []
    for name in costs:
        summary = cost_summary(costs[name].to_numpy(), alpha)
        rows.append({"strategy": name, **{"test_" + key: value for key, value in summary.items()},
                     **{"test_" + key: value for key, value in savings(baseline_mean, summary["mean_cost_eth"]).items()}})
    return costs, pd.DataFrame(rows)
