"""Independent evaluation of a fixed, scenario-independent schedule."""

from collections.abc import Mapping, Sequence
from math import fsum, isclose, isfinite

import numpy as np

from gasopt.types import OptimizationConfig, Scenario, Transaction, validate_problem

GWEI_TO_ETH = 1e-9


def mean_prices_gwei(scenarios: Sequence[Scenario]) -> tuple[float, ...]:
    """Probability-weighted slot prices; input probabilities must sum to one."""
    if not scenarios:
        raise ValueError("At least one scenario is required.")
    probabilities = [s.probability for s in scenarios]
    if not isclose(fsum(probabilities), 1.0, abs_tol=1e-12, rel_tol=0):
        raise ValueError("Scenario probabilities must sum to one.")
    horizon = len(scenarios[0].prices_gwei)
    if any(len(s.prices_gwei) != horizon for s in scenarios):
        raise ValueError("All scenarios must share the same horizon.")
    return tuple(float(p) for p in np.asarray(probabilities) @ np.asarray(
        [s.prices_gwei for s in scenarios], dtype=float))


def scenario_costs_eth(
    transactions: Sequence[Transaction],
    scenarios: Sequence[Scenario],
    schedule: Mapping[str, int],
    config: OptimizationConfig | None = None,
) -> dict[str, float]:
    """Validate the schedule, then sum gas * gwei/gas * 1e-9 per scenario."""
    config = config or OptimizationConfig()
    horizon = validate_problem(transactions, scenarios, config)
    if set(schedule) != {tx.id for tx in transactions}:
        raise ValueError("The schedule must assign exactly the supplied transactions.")
    for tx in transactions:
        slot = schedule[tx.id]
        if (isinstance(slot, bool) or not isinstance(slot, (int, np.integer))
                or not tx.release_slot <= slot <= tx.deadline):
            raise ValueError(f"Invalid slot or release/deadline violation for {tx.id}.")
    if config.slot_capacities is not None:
        for t in range(1, horizon + 1):
            if sum(slot == t for slot in schedule.values()) > config.slot_capacities[t - 1]:
                raise ValueError(f"Capacity exceeded in slot {t}.")
    return {s.id: GWEI_TO_ETH * fsum(tx.gas_used * s.prices_gwei[schedule[tx.id] - 1]
                                   for tx in transactions) for s in scenarios}


def weighted_var_cvar(
    costs_eth: Sequence[float], probabilities: Sequence[float], alpha: float,
) -> tuple[float, float]:
    """Lower weighted VaR and exact discrete CVaR (including fractional atoms).

    CVaR = min_eta [eta + sum_s q_s max(C_s - eta, 0)/(1-alpha)].
    A conditional average of costs >= VaR is generally incorrect for atoms.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between zero and one.")
    if len(costs_eth) == 0 or len(costs_eth) != len(probabilities):
        raise ValueError("Costs and probabilities must be nonempty and have equal lengths.")
    if any(not isfinite(c) for c in costs_eth):
        raise ValueError("Costs must be finite.")
    if any(not isfinite(q) or q < 0 for q in probabilities):
        raise ValueError("Probabilities must be finite and nonnegative.")
    if not isclose(fsum(probabilities), 1.0, abs_tol=1e-12, rel_tol=0):
        raise ValueError("Probabilities must sum to one.")
    ordered = sorted((c, q) for c, q in zip(costs_eth, probabilities) if q > 0)
    cumulative = 0.0
    eta = ordered[-1][0]
    for cost, probability in ordered:
        cumulative += probability
        # Decimal probability masses can land a few ulps below a boundary.
        if cumulative >= alpha or isclose(cumulative, alpha, abs_tol=1e-14, rel_tol=0):
            eta = cost
            break
    cvar = eta + fsum(q * max(c - eta, 0.0)
                      for c, q in zip(costs_eth, probabilities)) / (1.0 - alpha)
    return float(eta), float(cvar)
