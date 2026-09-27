"""A TRAIN-only service: no TEST data or evaluation service is accepted here."""
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import perf_counter
from dataclasses import asdict
from gasopt.api.highs_solver import solve_deterministic, solve_stochastic
from gasopt.types import OptimizationConfig

class TrainingOptimizer:
    def __init__(self, transactions, train, config, dataset_id):
        if any(not config.train_start.isoformat() <= s.id <= config.train_end.isoformat() for s in train):
            raise ValueError("Optimization requires exclusively TRAIN scenarios.")
        self.transactions, self.train, self.config = transactions, train, config
        self.dataset_id = dataset_id
        self._cache = OrderedDict()
        # APPSI/HiGHS output handling is not safe for concurrent in-process solves.
        self._lock = Lock()

    def solve(self, risk, alpha):
        if (1 - alpha) * len(self.train) + 1e-12 < self.config.min_train_tail_count:
            raise ValueError("Thin TRAIN tail: lower alpha to retain at least "
                             f"{self.config.min_train_tail_count:g} scenario equivalents.")
        key = (self.dataset_id, risk, alpha)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                result, duration = self._cache[key]
                return deepcopy(result), "cached_live", duration
            started = perf_counter()
            solve = solve_deterministic if risk == 0 else solve_stochastic
            result = solve(self.transactions, self.train, OptimizationConfig(alpha=alpha, lambda_risk=risk))
            duration = perf_counter() - started
            self._cache[key] = (result, duration)
            if len(self._cache) > 64:
                self._cache.popitem(last=False)
            return deepcopy(result), "live", duration
