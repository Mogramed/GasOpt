"""Manual checks of assignment, units and the mean-price optimum."""

import pytest

from gasopt.evaluation.metrics import mean_prices_gwei
from gasopt.models.deterministic import build_deterministic_model, solve_deterministic
from gasopt.types import OptimizationConfig


def test_manual_mean_price_optimum(toy):
    txs, scenarios = toy
    assert mean_prices_gwei(scenarios) == pytest.approx((12.8, 11.4, 8.8, 10.6))
    result = solve_deterministic(txs, scenarios)
    assert result.schedule == dict(zip((tx.id for tx in txs), (1, 2, 3, 3, 3)))
    # tx1: .0002688; tx2: .000741; remaining 348000 gas at 8.8 gwei/gas.
    manual = (21_000 * 12.8 + 65_000 * 11.4 + 348_000 * 8.8) * 1e-9
    assert manual == pytest.approx(0.0040722, abs=1e-12)
    assert result.expected_cost_eth == pytest.approx(manual, abs=1e-12)
    assert result.objective_value_eth == pytest.approx(manual, abs=1e-12)
    assert result.gas_cost_eth == result.expected_cost_eth
    assert result.scenario_costs_eth == pytest.approx({
        "s1": .003273, "s2": .003904, "s3": .005418, "s4": .004017, "s5": .003749}, abs=1e-12)
    assert result.solver_status == "optimal"
    assert result.optimality_gap == pytest.approx(0.0, abs=1e-9)


def test_assignments_binary_and_within_deadlines(toy):
    txs, scenarios = toy
    model = build_deterministic_model(txs, scenarios)
    assert all(variable.is_binary() for variable in model.x.values())
    assert len(model.x) == 14  # forbidden pairs are excluded, not relaxed
    result = solve_deterministic(txs, scenarios)
    assert result.num_variables == result.num_binary_variables == 14
    assert result.num_constraints == 5
    for tx in txs:
        values = [result.x_values[tx.id, t] for t in range(1, 5)]
        assert sum(values) == pytest.approx(1)
        assert all(min(abs(v), abs(v - 1)) <= 1e-9 for v in values)
        assert 1 <= result.schedule[tx.id] <= tx.deadline
        assert all(result.x_values[tx.id, t] == 0 for t in range(tx.deadline + 1, 5))


def test_deterministic_rejects_risk_penalty(toy):
    with pytest.raises(ValueError, match="lambda_risk=0"):
        build_deterministic_model(*toy, OptimizationConfig(lambda_risk=1))
