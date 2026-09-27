"""Serverless-safe HiGHS models used by the interactive API.

Pyomo's multiprocessing import hooks require POSIX semaphores that are not
available in the Vercel Python runtime.  The offline research pipeline keeps
its inspectable Pyomo models; this module expresses the same MILPs directly
through highspy for web requests.
"""

from collections.abc import Sequence
from math import fsum, isclose, isfinite

import highspy

from gasopt.evaluation.metrics import GWEI_TO_ETH, scenario_costs_eth, weighted_var_cvar
from gasopt.types import OptimizationConfig, OptimizationResult, Scenario, Transaction, validate_problem


def _solve(
    transactions: Sequence[Transaction],
    scenarios: Sequence[Scenario],
    config: OptimizationConfig,
) -> OptimizationResult:
    horizon = validate_problem(transactions, scenarios, config)
    solver = highspy.Highs()
    solver.silent()
    for key, value in {
        "threads": 1,
        "random_seed": 0,
        "mip_rel_gap": 0.0,
        "mip_abs_gap": 1e-10,
        "mip_feasibility_tolerance": 1e-9,
        "primal_feasibility_tolerance": 1e-9,
        "dual_feasibility_tolerance": 1e-9,
    }.items():
        solver.setOptionValue(key, value)

    x = {
        (tx.id, slot): solver.addBinary(name=f"x_{tx.id}_{slot}")
        for tx in transactions
        for slot in range(tx.release_slot, tx.deadline + 1)
    }
    for tx in transactions:
        solver.addConstr(
            sum(x[tx.id, slot] for slot in range(tx.release_slot, tx.deadline + 1)) == 1,
            name=f"assign_{tx.id}",
        )
    capacity_constraints = 0
    if config.slot_capacities is not None:
        for slot in range(1, horizon + 1):
            eligible = [x[tx.id, slot] for tx in transactions if (tx.id, slot) in x]
            if eligible:
                solver.addConstr(sum(eligible) <= config.slot_capacities[slot - 1], name=f"capacity_{slot}")
                capacity_constraints += 1

    scenario_expressions = {}
    for scenario in scenarios:
        scenario_expressions[scenario.id] = sum(
            GWEI_TO_ETH * tx.gas_used * scenario.prices_gwei[slot - 1] * variable
            for tx in transactions
            for slot in range(tx.release_slot, tx.deadline + 1)
            for variable in (x[tx.id, slot],)
        )
    expected_expression = sum(
        scenario.probability * scenario_expressions[scenario.id] for scenario in scenarios
    )

    eta = None
    excess = {}
    objective = expected_expression
    if config.lambda_risk > 0:
        eta = solver.addVariable(lb=-solver.inf, ub=solver.inf, name="eta")
        excess = {
            scenario.id: solver.addVariable(lb=0, ub=solver.inf, name=f"xi_{index}")
            for index, scenario in enumerate(scenarios)
        }
        for scenario in scenarios:
            solver.addConstr(
                excess[scenario.id] >= scenario_expressions[scenario.id] - eta,
                name=f"excess_{scenario.id}",
            )
        cvar_expression = eta + sum(
            scenario.probability * excess[scenario.id] for scenario in scenarios
        ) / (1 - config.alpha)
        objective = expected_expression + config.lambda_risk * cvar_expression

    solver.minimize(objective)
    if solver.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(f"HiGHS did not terminate optimally: {solver.modelStatusToString(solver.getModelStatus())}")

    values = {key: float(solver.val(variable)) for key, variable in x.items()}
    if any(min(abs(value), abs(value - 1.0)) > 1e-7 for value in values.values()):
        raise RuntimeError("Solver returned a nonbinary assignment.")
    schedule = {}
    for tx in transactions:
        selected = [slot for slot in range(tx.release_slot, tx.deadline + 1) if values[tx.id, slot] > 0.5]
        if len(selected) != 1:
            raise RuntimeError("Solver did not assign each transaction exactly once.")
        schedule[tx.id] = selected[0]
    x_values = {
        (tx.id, slot): values.get((tx.id, slot), 0.0)
        for tx in transactions
        for slot in range(1, horizon + 1)
    }

    costs = scenario_costs_eth(transactions, scenarios, schedule, config)
    probabilities = [scenario.probability for scenario in scenarios]
    expected = fsum(scenario.probability * costs[scenario.id] for scenario in scenarios)
    canonical_eta, canonical_cvar = weighted_var_cvar(
        [costs[scenario.id] for scenario in scenarios], probabilities, config.alpha
    )
    objective_value = float(solver.getObjectiveValue())
    independently_evaluated = expected + config.lambda_risk * canonical_cvar
    if not isclose(objective_value, independently_evaluated, rel_tol=1e-8, abs_tol=1e-10):
        raise RuntimeError("Solver objective and independently evaluated risk disagree.")

    info = solver.getInfo()
    bound = float(info.mip_dual_bound) if isfinite(info.mip_dual_bound) else None
    gap = float(info.mip_gap) if isfinite(info.mip_gap) else None
    solver_eta = float(solver.val(eta)) if eta is not None else None
    solver_cvar = None
    if eta is not None:
        solver_cvar = solver_eta + fsum(
            scenario.probability * float(solver.val(excess[scenario.id])) for scenario in scenarios
        ) / (1 - config.alpha)
    return OptimizationResult(
        schedule=schedule,
        x_values=x_values,
        expected_cost_eth=expected,
        eta_eth=canonical_eta,
        cvar_eth=canonical_cvar,
        scenario_costs_eth=costs,
        worst_case_cost_eth=max(costs.values()),
        objective_value_eth=objective_value,
        solver_status="optimal",
        solver_eta_eth=solver_eta,
        solver_cvar_eth=solver_cvar,
        num_variables=len(x) + (1 + len(scenarios) if eta is not None else 0),
        num_binary_variables=len(x),
        num_constraints=len(transactions) + capacity_constraints + (len(scenarios) if eta is not None else 0),
        objective_bound_eth=bound,
        optimality_gap=gap,
        node_count=int(info.mip_node_count),
    )


def solve_deterministic(
    transactions: Sequence[Transaction],
    scenarios: Sequence[Scenario],
    config: OptimizationConfig | None = None,
) -> OptimizationResult:
    config = config or OptimizationConfig()
    if config.lambda_risk != 0:
        raise ValueError("The deterministic model requires lambda_risk=0.")
    return _solve(transactions, scenarios, config)


def solve_stochastic(
    transactions: Sequence[Transaction],
    scenarios: Sequence[Scenario],
    config: OptimizationConfig | None = None,
) -> OptimizationResult:
    return _solve(transactions, scenarios, config or OptimizationConfig())
