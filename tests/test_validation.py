"""Reject malformed inputs before asking the solver for a schedule."""

from dataclasses import replace
import pytest

from gasopt.evaluation.metrics import scenario_costs_eth, weighted_var_cvar
from gasopt.models import solve_stochastic
from gasopt.types import OptimizationConfig, Scenario, Transaction


@pytest.mark.parametrize("kwargs", [{"alpha": 1}, {"alpha": 0}, {"alpha": float("nan")},
                                  {"lambda_risk": -1}, {"lambda_risk": float("inf")},
                                  {"slot_capacities": (1, -1)}, {"slot_capacities": (1.5,)}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        OptimizationConfig(**kwargs)


@pytest.mark.parametrize("gas, deadline", [(0, 1), (-1, 1), (1, 0), (1.5, 1), (1, 1.5), (True, 1)])
def test_invalid_transaction(gas, deadline):
    with pytest.raises(ValueError):
        Transaction("bad", gas, deadline)


@pytest.mark.parametrize("prices, probability", [((-1,), 1), ((float("nan"),), 1),
                                                ((), 1), ((1,), -.1), ((1,), float("inf"))])
def test_invalid_scenario(prices, probability):
    with pytest.raises(ValueError):
        Scenario("bad", prices, probability)


def test_problem_validation(toy):
    txs, scenarios = toy
    invalid = [
        ((), scenarios, OptimizationConfig()),
        (txs, (), OptimizationConfig()),
        (txs + (txs[0],), scenarios, OptimizationConfig()),
        (txs, scenarios + (scenarios[0],), OptimizationConfig()),
        (txs, scenarios[:-1], OptimizationConfig()),
        (txs, (replace(scenarios[0], prices_gwei=(1,)),) + scenarios[1:], OptimizationConfig()),
        ((replace(txs[0], deadline=5),) + txs[1:], scenarios, OptimizationConfig()),
        (txs, scenarios, OptimizationConfig(slot_capacities=(1,))),
    ]
    for args in invalid:
        with pytest.raises(ValueError):
            solve_stochastic(*args)


def test_schedule_validation(toy):
    txs, scenarios = toy
    good = dict(zip((tx.id for tx in txs), (1, 2, 3, 3, 3)))
    for bad in ({}, {**good, "extra": 1}, {**good, "tx1": 2}, {**good, "tx2": 1.5}):
        with pytest.raises(ValueError):
            scenario_costs_eth(txs, scenarios, bad)
    with pytest.raises(ValueError, match="Capacity exceeded"):
        scenario_costs_eth(txs, scenarios, good, OptimizationConfig(slot_capacities=(1, 1, 1, 2)))


@pytest.mark.parametrize("costs, probs, alpha", [([], [], .8), ([1], [.2], .8),
    ([1], [1, 0], .8), ([1], [-1], .8), ([float("nan")], [1], .8), ([1], [1], 1)])
def test_invalid_metrics(costs, probs, alpha):
    with pytest.raises(ValueError):
        weighted_var_cvar(costs, probs, alpha)
