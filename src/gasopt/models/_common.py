"""Shared assignment constraints, HiGHS execution and independent evaluation."""

from collections.abc import Sequence
from math import fsum, isclose, isfinite

import pyomo.environ as pyo
from pyomo.contrib.appsi.base import TerminationCondition
from pyomo.contrib.appsi.solvers import Highs

from gasopt.evaluation.metrics import scenario_costs_eth, weighted_var_cvar
from gasopt.types import OptimizationConfig, OptimizationResult, Scenario, Transaction, validate_problem


def assignment_model(
    transactions: Sequence[Transaction], scenarios: Sequence[Scenario], config: OptimizationConfig,
) -> pyo.ConcreteModel:
    """Build x_it only for r_i <= t <= d_i; other slots are implicitly zero."""
    horizon = validate_problem(transactions, scenarios, config)
    model = pyo.ConcreteModel(name="GasOpt static scheduling")
    model.I = pyo.Set(initialize=[tx.id for tx in transactions], ordered=True)
    model.T = pyo.RangeSet(1, horizon)
    model.A = pyo.Set(dimen=2, initialize=[
        (tx.id, t) for tx in transactions for t in range(tx.release_slot, tx.deadline + 1)])
    model.x = pyo.Var(model.A, domain=pyo.Binary)
    deadlines = {tx.id: tx.deadline for tx in transactions}
    releases = {tx.id: tx.release_slot for tx in transactions}
    model.assign_once = pyo.Constraint(model.I, rule=lambda m, i:
        sum(m.x[i, t] for t in range(releases[i], deadlines[i] + 1)) == 1)
    if config.slot_capacities is not None:
        def capacity_rule(m: pyo.ConcreteModel, t: int):
            eligible = [i for i in m.I if (i, t) in m.A]
            if not eligible:
                return pyo.Constraint.Skip
            return sum(m.x[i, t] for i in eligible) <= config.slot_capacities[t - 1]
        model.capacity = pyo.Constraint(model.T, rule=capacity_rule)
    return model


def solve_and_evaluate(
    model: pyo.ConcreteModel, transactions: Sequence[Transaction],
    scenarios: Sequence[Scenario], config: OptimizationConfig,
) -> OptimizationResult:
    """Require optimal termination before loading a solution; audit its cost."""
    solver = Highs()
    if not solver.available():
        raise RuntimeError("HiGHS is unavailable. Install the highspy dependency.")
    solver.config.load_solution = False
    solver.highs_options.update({
        "threads": 1, "random_seed": 0, "mip_rel_gap": 0.0,
        "mip_abs_gap": 1e-10, "mip_feasibility_tolerance": 1e-9,
        "primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9,
    })
    solved = solver.solve(model)
    if solved.termination_condition != TerminationCondition.optimal:
        raise RuntimeError(f"HiGHS did not terminate optimally: {solved.termination_condition.name}")
    solved.solution_loader.load_vars()
    x_values = {(tx.id, t): float(pyo.value(model.x[tx.id, t]))
                if (tx.id, t) in model.A else 0.0
                for tx in transactions for t in model.T}
    if any(min(abs(v), abs(v - 1.0)) > 1e-7 for v in x_values.values()):
        raise RuntimeError("Solver returned a nonbinary assignment.")
    schedule = {}
    for tx in transactions:
        selected = [t for t in model.T if x_values[tx.id, t] > 0.5]
        if len(selected) != 1:
            raise RuntimeError("Solver did not assign each transaction exactly once.")
        schedule[tx.id] = selected[0]
    costs = scenario_costs_eth(transactions, scenarios, schedule, config)
    probabilities = [s.probability for s in scenarios]
    expected = fsum(s.probability * costs[s.id] for s in scenarios)
    eta, cvar = weighted_var_cvar([costs[s.id] for s in scenarios], probabilities, config.alpha)
    objective = float(pyo.value(model.objective))
    if not isclose(objective, expected + config.lambda_risk * cvar, rel_tol=1e-8, abs_tol=1e-10):
        raise RuntimeError("Solver objective and independently evaluated risk disagree.")
    bound = solved.best_objective_bound
    bound = float(bound) if bound is not None and isfinite(bound) else None
    gap = abs(objective - bound) / max(abs(objective), 1e-12) if bound is not None else None
    variables = list(model.component_data_objects(pyo.Var))
    return OptimizationResult(
        schedule=schedule, x_values=x_values, expected_cost_eth=expected,
        eta_eth=eta, cvar_eth=cvar, scenario_costs_eth=costs,
        worst_case_cost_eth=max(costs.values()), objective_value_eth=objective,
        solver_status=solved.termination_condition.name,
        solver_eta_eth=float(pyo.value(model.eta)) if hasattr(model, "eta") else None,
        solver_cvar_eth=float(pyo.value(model.cvar)) if hasattr(model, "cvar") else None,
        num_variables=len(variables), num_binary_variables=sum(v.is_binary() for v in variables),
        num_constraints=sum(1 for _ in model.component_data_objects(pyo.Constraint, active=True)),
        objective_bound_eth=bound, optimality_gap=gap,
        # APPSI does not expose a public node count: do not invent one.
        node_count=None,
    )
