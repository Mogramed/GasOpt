"""Fixed-date experiment configuration; no dependence on the current date."""

from dataclasses import asdict, dataclass
from datetime import date
from math import isfinite
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ExperimentConfig:
    """Inclusive UTC date ranges and prespecified empirical study settings."""

    train_start: date
    train_end: date
    test_start: date
    test_end: date
    alpha: float = .95
    lambda_grid: tuple[float, ...] = (0, .05, .1, .25, .5, .75, 1, 1.5, 2, 3, 5)
    min_train_tail_count: float = 10
    max_missing_day_fraction: float = .05
    transaction_count: int = 30
    sample_seed: int = 20260923
    sample_per_day: int = 64
    gas_used_min: int = 21_000
    gas_used_max: int = 1_000_000
    workload_trim_lower: float = .01
    workload_trim_upper: float = .99
    dune_gas_price_unit: str = "wei"
    urgent_window: int = 2
    standard_window: int = 4
    flexible_window: int = 8

    def __post_init__(self) -> None:
        for field in ("train_start", "train_end", "test_start", "test_end"):
            value = getattr(self, field)
            object.__setattr__(self, field, date.fromisoformat(value) if isinstance(value, str) else value)
        object.__setattr__(self, "lambda_grid", tuple(self.lambda_grid))
        if not self.train_start <= self.train_end < self.test_start <= self.test_end:
            raise ValueError("TRAIN must occur strictly before TEST with no overlap.")
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must be in (0, 1).")
        if (not self.lambda_grid or len(set(self.lambda_grid)) != len(self.lambda_grid)
                or any(not isfinite(x) or x < 0 for x in self.lambda_grid)):
            raise ValueError("lambda_grid must contain unique finite nonnegative weights.")
        if not 0 <= self.max_missing_day_fraction < 1:
            raise ValueError("Invalid missing-day tolerance.")
        if not isfinite(self.min_train_tail_count) or self.min_train_tail_count <= 0:
            raise ValueError("min_train_tail_count must be positive.")
        if not 0 <= self.workload_trim_lower < self.workload_trim_upper <= 1:
            raise ValueError("Invalid workload trimming quantiles.")
        for name in ("transaction_count", "sample_per_day", "gas_used_min", "gas_used_max",
                     "urgent_window", "standard_window", "flexible_window"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if any(x > 12 for x in (self.urgent_window, self.standard_window, self.flexible_window)):
            raise ValueError("Execution windows cannot exceed 12 slots.")
        if self.gas_used_min > self.gas_used_max or self.dune_gas_price_unit not in ("wei", "gwei"):
            raise ValueError("Invalid gas range or raw gas-price unit.")
        if isinstance(self.sample_seed, bool) or not isinstance(self.sample_seed, int) or self.sample_seed < 0:
            raise ValueError("sample_seed must be a nonnegative integer.")

    def to_dict(self) -> dict:
        """Return a JSON-compatible snapshot for provenance."""
        result = asdict(self)
        return {key: value.isoformat() if isinstance(value, date) else value for key, value in result.items()}


def load_config(path: str | Path = "config/empirical.toml") -> ExperimentConfig:
    """Load a small TOML file with strict, explicit fields."""
    with Path(path).open("rb") as stream:
        return ExperimentConfig(**tomllib.load(stream))
