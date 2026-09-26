"""Separate, explicitly pedagogical LP-bound illustration (not a HiGHS trace)."""
from functools import lru_cache
import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs
from pyomo.contrib.appsi.base import TerminationCondition

@lru_cache(maxsize=1)
def branch_demo():
    nodes = []
    for name, parent, fixed in [('root', None, {}), ('x0', 'root', {'x': 0}),
                                ('x1', 'root', {'x': 1}), ('y0', 'x1', {'x': 1, 'y': 0}),
                                ('y1', 'x1', {'x': 1, 'y': 1})]:
        m = pyo.ConcreteModel()
        m.x = pyo.Var(bounds=(0, 1)); m.y = pyo.Var(bounds=(0, 1))
        m.requirement = pyo.Constraint(expr=2*m.x + 2*m.y >= 3)
        m.objective = pyo.Objective(expr=3*m.x + 2*m.y)
        for key, value in fixed.items():
            getattr(m, key).fix(value)
        solver = Highs(); solver.config.load_solution = False
        solver.highs_options['threads'] = 1
        r = solver.solve(m)
        feasible = r.termination_condition == TerminationCondition.optimal
        if feasible:
            r.solution_loader.load_vars()
        nodes.append({'id': name, 'parent': parent, 'fixed': fixed,
                      'bound': float(pyo.value(m.objective)) if feasible else None,
                      'x': float(pyo.value(m.x)) if feasible else None,
                      'y': float(pyo.value(m.y)) if feasible else None,
                      'status': 'infeasible' if not feasible else ('integer incumbent' if name == 'y1' else 'fractional relaxation'),
                      'reason': 'Prune: infeasible' if not feasible else ('Integer feasible; incumbent = 5' if name == 'y1' else 'Branch on a fractional variable')})
    return {'label': 'Pedagogical Branch-and-Bound illustration',
            'disclaimer': 'Not the execution trace of the empirical Ethereum model.',
            'formulation': r'\min\ 3x+2y\quad\text{s.t. }2x+2y\geq3,\quad x,y\in\{0,1\}',
            'nodes': nodes, 'optimum': 5,
            'bound_pruning': 'A node can also be pruned when its lower bound cannot improve the incumbent. This small example needs only infeasibility and integrality pruning.'}
