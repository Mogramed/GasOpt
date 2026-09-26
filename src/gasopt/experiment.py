"""Reproducible Phase 1 sensitivity experiment; no external data access."""

import pandas as pd

from gasopt.data.synthetic import toy_data
from gasopt.models import solve_deterministic, solve_stochastic
from gasopt.types import OptimizationConfig


def sensitivity_table() -> pd.DataFrame:
    """Run the requested risk weights on the exact synthetic dataset."""
    transactions, scenarios = toy_data()
    rows = []
    # Five scenarios make alpha=.80 pedagogical. A future real-data experiment
    # can use alpha=.95 with many more scenarios and a sufficiently populated tail.
    for risk in (0.0, 0.1, 0.25, 0.5, 1.0):
        result = solve_stochastic(transactions, scenarios, OptimizationConfig(lambda_risk=risk))
        rows.append({"lambda_risk": risk, "expected_cost_eth": result.expected_cost_eth,
                     "cvar_eth": result.cvar_eth, "worst_case_cost_eth": result.worst_case_cost_eth,
                     "eta_eth": result.eta_eth, "objective_value_eth": result.objective_value_eth,
                     "schedule_tx1_to_tx5": tuple(result.schedule[tx.id] for tx in transactions),
                     "solver_status": result.solver_status})
    return pd.DataFrame(rows)


def main() -> None:
    """Print mean-price validation and the complete synthetic sensitivity table."""
    transactions, scenarios = toy_data()
    deterministic = solve_deterministic(transactions, scenarios)
    print("SYNTHETIC PHASE 1 DATA - not empirical Ethereum observations")
    print(f"Deterministic schedule: {deterministic.schedule}")
    print(f"Expected gas cost: {deterministic.expected_cost_eth:.9f} ETH")
    print(sensitivity_table().to_string(index=False, float_format=lambda value: f"{value:.9f}"))


if __name__ == "__main__":
    main()
