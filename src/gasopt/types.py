"""Typed inputs and outputs; all reported monetary quantities are in ETH."""

from dataclasses import dataclass
from math import isclose, isfinite
from numbers import Integral
from collections.abc import Sequence


@dataclass(frozen=True)
class Transaction:
    """Gas requirement and an inclusive one-based release/deadline window."""

    id: str
    gas_used: int
    deadline: int
    release_slot: int = 1
    priority_class: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Transaction id must be nonempty.")
        for name, value in (("gas_used", self.gas_used), ("deadline", self.deadline),
                            ("release_slot", self.release_slot)):
            if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if self.release_slot > self.deadline:
            raise ValueError("release_slot cannot exceed deadline.")


@dataclass(frozen=True)
class Scenario:
    """One complete gas-price trajectory (gwei/gas) and its probability."""

    id: str
    prices_gwei: tuple[float, ...]
    probability: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "prices_gwei", tuple(self.prices_gwei))
        if not self.id or not self.prices_gwei:
            raise ValueError("Scenario id and price trajectory must be nonempty.")
        if any(not isfinite(p) or p < 0 for p in self.prices_gwei):
            raise ValueError("Gas prices must be finite and nonnegative.")
        if not isfinite(self.probability) or self.probability < 0:
            raise ValueError("Scenario probability must be finite and nonnegative.")


@dataclass(frozen=True)
class OptimizationConfig:
    """Risk settings and optional per-slot transaction-count capacities."""

    alpha: float = 0.80
    lambda_risk: float = 0.0
    slot_capacities: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.alpha) or not 0 < self.alpha < 1:
            raise ValueError("alpha must be strictly between zero and one.")
        if not isfinite(self.lambda_risk) or self.lambda_risk < 0:
            raise ValueError("lambda_risk must be finite and nonnegative.")
        if self.slot_capacities is not None:
            object.__setattr__(self, "slot_capacities", tuple(self.slot_capacities))
            if any(isinstance(k, bool) or not isinstance(k, Integral) or k < 0
                   for k in self.slot_capacities):
                raise ValueError("Slot capacities must be nonnegative integers.")


@dataclass(frozen=True)
class OptimizationResult:
    """A here-and-now schedule and independently evaluated ETH cost/risk.

    eta_eth is the canonical lower weighted alpha-quantile. solver_eta_eth
    records the solver's possibly nonunique CVaR threshold (None at lambda=0).
    x_values contains raw solver values, padded with zero for forbidden slots.
    """

    schedule: dict[str, int]
    x_values: dict[tuple[str, int], float]
    expected_cost_eth: float
    eta_eth: float
    cvar_eth: float
    scenario_costs_eth: dict[str, float]
    worst_case_cost_eth: float
    objective_value_eth: float
    solver_status: str
    solver_eta_eth: float | None
    solver_cvar_eth: float | None
    num_variables: int
    num_binary_variables: int
    num_constraints: int
    objective_bound_eth: float | None
    optimality_gap: float | None
    node_count: int | None = None

    @property
    def gas_cost_eth(self) -> float:
        """Expected gas expenditure, excluding the objective's risk penalty."""
        return self.expected_cost_eth


def validate_problem(
    transactions: Sequence[Transaction],
    scenarios: Sequence[Scenario],
    config: OptimizationConfig,
) -> int:
    """Validate a common horizon, identifiers, probabilities and deadlines."""
    if not transactions or not scenarios:
        raise ValueError("At least one transaction and one scenario are required.")
    if len({tx.id for tx in transactions}) != len(transactions):
        raise ValueError("Transaction ids must be unique.")
    if len({s.id for s in scenarios}) != len(scenarios):
        raise ValueError("Scenario ids must be unique.")
    horizon = len(scenarios[0].prices_gwei)
    if any(len(s.prices_gwei) != horizon for s in scenarios):
        raise ValueError("All scenarios must share the same horizon.")
    if not isclose(sum(s.probability for s in scenarios), 1.0, abs_tol=1e-12, rel_tol=0):
        raise ValueError("Scenario probabilities must sum to one; no silent normalization.")
    if any(tx.deadline > horizon for tx in transactions):
        raise ValueError("Deadlines cannot exceed the scenario horizon.")
    if config.slot_capacities is not None and len(config.slot_capacities) != horizon:
        raise ValueError("Provide one capacity for each slot.")
    return horizon
