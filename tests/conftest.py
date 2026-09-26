"""Shared deterministic synthetic fixture and independent exhaustive oracle."""

from itertools import product
import pytest

from gasopt.data.synthetic import toy_data


@pytest.fixture
def toy():
    return toy_data()


def exhaustive_solutions(transactions, scenarios, alpha, risk, capacities=None):
    """Enumerate schedules; compute CVaR by filling the upper probability tail.

    This test oracle does not reuse the production cost or CVaR functions.
    It is only appropriate for the 96-schedule pedagogical instance.
    """
    rows = []
    for slots in product(*(range(1, tx.deadline + 1) for tx in transactions)):
        if capacities is not None and any(slots.count(t) > k for t, k in enumerate(capacities, 1)):
            continue
        costs = [sum(tx.gas_used * s.prices_gwei[t - 1]
                     for tx, t in zip(transactions, slots)) / 1_000_000_000 for s in scenarios]
        expected = sum(s.probability * cost for s, cost in zip(scenarios, costs))
        tail_mass = 1 - alpha
        tail_cost = 0.0
        for cost, probability in sorted(zip(costs, (s.probability for s in scenarios)), reverse=True):
            take = min(probability, tail_mass)
            tail_cost += take * cost
            tail_mass -= take
            if tail_mass <= 1e-15:
                break
        cvar = tail_cost / (1 - alpha)
        rows.append((expected + risk * cvar, slots))
    return rows
