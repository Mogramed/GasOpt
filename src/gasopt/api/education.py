"""Separate, explicitly pedagogical branch-and-bound illustration."""
from functools import lru_cache

@lru_cache(maxsize=1)
def branch_demo():
    nodes = [
        {'id': 'root', 'parent': None, 'fixed': {}, 'bound': 3.5, 'x': .5, 'y': 1.0,
         'status': 'fractional relaxation', 'reason': 'Branch on a fractional variable'},
        {'id': 'x0', 'parent': 'root', 'fixed': {'x': 0}, 'bound': None, 'x': None, 'y': None,
         'status': 'infeasible', 'reason': 'Prune: infeasible'},
        {'id': 'x1', 'parent': 'root', 'fixed': {'x': 1}, 'bound': 4.0, 'x': 1.0, 'y': .5,
         'status': 'fractional relaxation', 'reason': 'Branch on a fractional variable'},
        {'id': 'y0', 'parent': 'x1', 'fixed': {'x': 1, 'y': 0}, 'bound': None, 'x': None, 'y': None,
         'status': 'infeasible', 'reason': 'Prune: infeasible'},
        {'id': 'y1', 'parent': 'x1', 'fixed': {'x': 1, 'y': 1}, 'bound': 5.0, 'x': 1.0, 'y': 1.0,
         'status': 'integer incumbent', 'reason': 'Integer feasible; incumbent = 5'},
    ]
    return {'label': 'Pedagogical Branch-and-Bound illustration',
            'disclaimer': 'Not the execution trace of the empirical Ethereum model.',
            'formulation': r'\min\ 3x+2y\quad\text{s.t. }2x+2y\geq3,\quad x,y\in\{0,1\}',
            'nodes': nodes, 'optimum': 5,
            'bound_pruning': 'A node can also be pruned when its lower bound cannot improve the incumbent. This small example needs only infeasibility and integrality pruning.'}
