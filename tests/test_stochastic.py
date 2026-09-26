"""Equivalence, feasibility and independent optimality verification."""

from dataclasses import replace
import pytest

from conftest import exhaustive_solutions
from gasopt.models import solve_deterministic, solve_stochastic
from gasopt.types import OptimizationConfig


@pytest.mark.parametrize("probabilities", [(0.2,) * 5, (0.05, 0.1, 0.15, 0.3, 0.4), (0, 0, 1, 0, 0)])
@pytest.mark.parametrize("capacities", [None, (2, 1, 1, 2)])
def test_mean_and_expected_value_equivalence(toy, probabilities, capacities):
    txs, paths = toy
    scenarios = tuple(replace(s, probability=q) for s, q in zip(paths, probabilities))
    config = OptimizationConfig(slot_capacities=capacities)
    deterministic = solve_deterministic(txs, scenarios, config)
    stochastic = solve_stochastic(txs, scenarios, config)
    assert stochastic.objective_value_eth == pytest.approx(deterministic.objective_value_eth, abs=1e-11)
    # Equivalent objectives/optimal sets need not give identical schedules under ties.
    assert stochastic.solver_status == deterministic.solver_status == "optimal"
    assert stochastic.solver_eta_eth is None
    oracle = exhaustive_solutions(txs, scenarios, .8, 0, capacities)
    assert stochastic.expected_cost_eth == pytest.approx(min(row[0] for row in oracle), abs=1e-11)


@pytest.mark.parametrize("risk", [0, .1, .25, .5, 1])
@pytest.mark.parametrize("capacities", [None, (2, 1, 1, 2)])
def test_stochastic_matches_exhaustive_search(toy, risk, capacities):
    txs, scenarios = toy
    result = solve_stochastic(txs, scenarios, OptimizationConfig(lambda_risk=risk, slot_capacities=capacities))
    rows = exhaustive_solutions(txs, scenarios, .8, risk, capacities)
    if capacities is None:
        assert len(rows) == 96
    assert result.objective_value_eth == pytest.approx(min(row[0] for row in rows), abs=1e-10)
    assert result.solver_status == "optimal"
    for tx in txs:
        assert sum(result.x_values[tx.id, t] for t in range(1, 5)) == pytest.approx(1)
        assert result.schedule[tx.id] <= tx.deadline
    assert all(min(abs(v), abs(v - 1)) <= 1e-9 for v in result.x_values.values())
    if capacities:
        assert all(list(result.schedule.values()).count(t) <= k for t, k in enumerate(capacities, 1))


def test_infeasible_capacity_fails_without_loading_solution(toy):
    with pytest.raises(RuntimeError, match="infeasible"):
        solve_stochastic(*toy, OptimizationConfig(slot_capacities=(0, 5, 5, 5)))
