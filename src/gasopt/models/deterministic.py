"""Minimize gas expenditure against probability-weighted mean slot prices."""

from collections.abc import Sequence
import pyomo.environ as pyo

from gasopt.evaluation.metrics import GWEI_TO_ETH, mean_prices_gwei
from gasopt.models._common import assignment_model, solve_and_evaluate
from gasopt.types import OptimizationConfig, OptimizationResult, Scenario, Transaction


def build_deterministic_model(
    transactions: Sequence[Transaction], scenarios: Sequence[Scenario],
    config: OptimizationConfig | None = None,
) -> pyo.ConcreteModel:
    """Expose the mean-price MILP; risk aversion must be zero."""
    config = config or OptimizationConfig()
    if config.lambda_risk != 0:
        raise ValueError("The deterministic model requires lambda_risk=0.")
    model = assignment_model(transactions, scenarios, config)
    means = mean_prices_gwei(scenarios)
    gas = {tx.id: tx.gas_used for tx in transactions}
    model.objective = pyo.Objective(expr=GWEI_TO_ETH * sum(
        gas[i] * means[t - 1] * model.x[i, t] for i, t in model.A), sense=pyo.minimize)
    return model


def solve_deterministic(
    transactions: Sequence[Transaction], scenarios: Sequence[Scenario],
    config: OptimizationConfig | None = None,
) -> OptimizationResult:
    """Solve a single here-and-now schedule using mean prices."""
    config = config or OptimizationConfig()
    return solve_and_evaluate(build_deterministic_model(transactions, scenarios, config),
                              transactions, scenarios, config)
