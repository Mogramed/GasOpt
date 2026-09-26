"""Finite-scenario expected-cost and mean-plus-CVaR MILPs (no recourse)."""

from collections.abc import Sequence
import pyomo.environ as pyo

from gasopt.evaluation.metrics import GWEI_TO_ETH
from gasopt.models._common import assignment_model, solve_and_evaluate
from gasopt.types import OptimizationConfig, OptimizationResult, Scenario, Transaction


def build_stochastic_model(
    transactions: Sequence[Transaction], scenarios: Sequence[Scenario],
    config: OptimizationConfig | None = None,
) -> pyo.ConcreteModel:
    """Build explicit C_s(x), E[C] and, for positive lambda, the CVaR epigraph.

    With lambda=0 the unused eta/xi variables are omitted. The optimal schedule
    still receives an independently calculated VaR/CVaR in the returned result.
    """
    config = config or OptimizationConfig()
    model = assignment_model(transactions, scenarios, config)
    gas = {tx.id: tx.gas_used for tx in transactions}
    paths = {s.id: s for s in scenarios}
    model.S = pyo.Set(initialize=list(paths), ordered=True)
    model.scenario_cost = pyo.Expression(model.S, rule=lambda m, s: GWEI_TO_ETH * sum(
        gas[i] * paths[s].prices_gwei[t - 1] * m.x[i, t] for i, t in m.A))
    model.expected_cost = pyo.Expression(expr=sum(
        paths[s].probability * model.scenario_cost[s] for s in model.S))
    objective = model.expected_cost
    if config.lambda_risk > 0:
        model.eta = pyo.Var(domain=pyo.Reals)
        model.xi = pyo.Var(model.S, domain=pyo.NonNegativeReals)
        model.excess = pyo.Constraint(model.S, rule=lambda m, s:
            m.xi[s] >= m.scenario_cost[s] - m.eta)
        model.cvar = pyo.Expression(expr=model.eta + sum(
            paths[s].probability * model.xi[s] for s in model.S) / (1 - config.alpha))
        objective = objective + config.lambda_risk * model.cvar
    model.objective = pyo.Objective(expr=objective, sense=pyo.minimize)
    return model


def solve_stochastic(
    transactions: Sequence[Transaction], scenarios: Sequence[Scenario],
    config: OptimizationConfig | None = None,
) -> OptimizationResult:
    """Optimize one schedule across all scenarios and return audited ETH costs."""
    config = config or OptimizationConfig()
    return solve_and_evaluate(build_stochastic_model(transactions, scenarios, config),
                              transactions, scenarios, config)
