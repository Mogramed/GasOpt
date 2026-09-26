"""Data-frame and visual encodings; scientific metrics are delegated to the core."""
import json
from hashlib import sha256
from math import fsum
import pandas as pd
from gasopt.evaluation.metrics import weighted_var_cvar

def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15))

def schedule_id(schedule: dict[str, int]) -> str:
    return sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest()[:10]

def cost_points(costs: dict[str, float], alpha: float) -> list[dict]:
    """Encode sorted costs, excesses and fractional tail mass for visualization.

    VaR/CVaR come from weighted_var_cvar. The fractional atom annotation is a
    visual partition of probability mass, not an alternative risk estimator.
    """
    n = len(costs)
    eta, _ = weighted_var_cvar(list(costs.values()), [1 / n] * n, alpha)
    rows = []
    for index, (day, cost) in enumerate(sorted(costs.items(), key=lambda x: (x[1], x[0]))):
        cumulative = (index + 1) / n
        rows.append({"date": day, "cost_eth": cost, "probability": 1 / n,
                     "eta_eth": eta, "xi_eth": max(cost - eta, 0), "rank": index + 1,
                     "cumulative_probability": cumulative,
                     "tail_mass": max(0, cumulative - max(index / n, alpha))})
    assert abs(fsum(row["tail_mass"] for row in rows) - (1 - alpha)) < 1e-12
    return rows

def utc_range(slot: int) -> str:
    return f"{2 * (slot - 1):02d}:00–{2 * slot:02d}:00 UTC"
