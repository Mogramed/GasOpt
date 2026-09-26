"""Tail atoms, solver epigraphs and the actual risk-aversion tradeoff."""

import pyomo.environ as pyo
import pytest

from conftest import exhaustive_solutions
from gasopt.evaluation.metrics import weighted_var_cvar
from gasopt.models._common import solve_and_evaluate
from gasopt.models.stochastic_cvar import build_stochastic_model, solve_stochastic
from gasopt.types import OptimizationConfig, Scenario, Transaction


@pytest.mark.parametrize("costs, probabilities, alpha, expected", [
    ([1, 2, 3, 4, 5], [.2] * 5, .8, (4, 5)),
    ([1, 2, 3, 4, 5], [.2] * 5, .7, (4, 14 / 3)),
    ([1, 2, 10], [.5, .4, .1], .8, (2, 6)),
    ([2, 2, 10], [.5, .4, .1], .8, (2, 6)),
    ([3, 3], [.2, .8], .95, (3, 3)),
    ([100, 2], [0, 1], .8, (2, 2)),
    ([1, 2, 3], [.7, .1, .2], .8, (2, 3)),
])
def test_exact_discrete_cvar(costs, probabilities, alpha, expected):
    assert weighted_var_cvar(costs, probabilities, alpha) == pytest.approx(expected)


@pytest.mark.parametrize("risk", [.1, .25, .5, 1])
def test_epigraph_and_independent_risk_agree(toy, risk):
    config = OptimizationConfig(lambda_risk=risk)
    model = build_stochastic_model(*toy, config)
    result = solve_and_evaluate(model, *toy, config)
    assert result.num_variables == 20  # 14 binaries, eta, five excesses
    assert result.num_binary_variables == 14
    assert result.num_constraints == 10
    for s in model.S:
        assert pyo.value(model.xi[s]) >= -1e-10
        assert pyo.value(model.xi[s]) >= pyo.value(model.scenario_cost[s] - model.eta) - 1e-10
        assert pyo.value(model.scenario_cost[s]) == pytest.approx(result.scenario_costs_eth[s], abs=1e-11)
    assert result.solver_cvar_eth == pytest.approx(result.cvar_eth, abs=1e-10)
    assert result.cvar_eth == pytest.approx(result.worst_case_cost_eth, abs=1e-11)
    assert result.objective_value_eth == pytest.approx(result.expected_cost_eth + risk * result.cvar_eth, abs=1e-10)


def test_zero_risk_still_reports_meaningful_tail_metrics(toy):
    result = solve_stochastic(*toy)
    assert result.eta_eth == pytest.approx(.004017, abs=1e-12)
    assert result.cvar_eth == pytest.approx(.005418, abs=1e-12)
    assert result.solver_eta_eth is None and result.solver_cvar_eth is None


def test_risk_aversion_changes_schedule_at_one(toy):
    low = solve_stochastic(*toy)
    high = solve_stochastic(*toy, OptimizationConfig(lambda_risk=1))
    assert tuple(high.schedule.values()) == (1, 2, 3, 3, 4)
    assert high.expected_cost_eth == pytest.approx(.0043962, abs=1e-12)
    assert high.cvar_eth == pytest.approx(.005058, abs=1e-12)
    assert high.eta_eth == pytest.approx(.004917, abs=1e-12)
    assert high.expected_cost_eth > low.expected_cost_eth
    assert high.cvar_eth < low.cvar_eth


def test_unequal_probability_cvar_milp():
    txs = (Transaction("a", 21_000, 2), Transaction("b", 65_000, 2))
    scenarios = (Scenario("low", (1, 3), .5), Scenario("middle", (2, 3), .4),
                 Scenario("spike", (10, 3), .1))
    config = OptimizationConfig(alpha=.8, lambda_risk=1)
    result = solve_stochastic(txs, scenarios, config)
    rows = exhaustive_solutions(txs, scenarios, .8, 1)
    assert result.objective_value_eth == pytest.approx(min(row[0] for row in rows), abs=1e-11)
    assert result.solver_cvar_eth == pytest.approx(result.cvar_eth, abs=1e-11)
