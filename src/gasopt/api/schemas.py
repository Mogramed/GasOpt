"""Public, JSON-only application contracts."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt

class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class SolveRequest(RequestModel):
    lambda_risk: Annotated[float, Field(ge=0, strict=True)] = 0
    alpha: Annotated[float, Field(gt=0, lt=1, strict=True)] = .95

class ScheduleRequest(RequestModel):
    schedule: dict[str, StrictInt]
    alpha: Annotated[float, Field(gt=0, lt=1, strict=True)] = .95

class ComparisonRequest(RequestModel):
    schedule_a: dict[str, StrictInt]
    schedule_b: dict[str, StrictInt]
    alpha: Annotated[float, Field(gt=0, lt=1, strict=True)] = .95

class ScenarioRequest(ScheduleRequest):
    split: Literal["TRAIN", "TEST"] = "TRAIN"
    day: str | None = None
    selector: Literal["typical", "high", "worst"] = "typical"

class CalculatorRequest(RequestModel):
    transaction_id: str
    day: str
    slot: StrictInt

class CostPoint(BaseModel):
    date: str
    cost_eth: float
    probability: float
    eta_eth: float
    xi_eth: float
    rank: int
    cumulative_probability: float
    tail_mass: float

class SolveResponse(BaseModel):
    origin: Literal["live", "cached_live", "archived"]
    dataset_id: str
    strategy: str
    schedule_id: str
    lambda_risk: float
    alpha: float
    exploratory: bool
    schedule: dict[str, int]
    assignments: list[dict]
    expected_cost_eth: float
    var_eth: float
    cvar_eth: float
    worst_case_cost_eth: float
    objective_value_eth: float
    solver_status: str
    objective_bound_eth: float | None
    optimality_gap: float | None
    num_variables: int
    num_binary_variables: int
    num_constraints: int
    node_count: int | None = None
    tail_scenario_count: float
    scenario_costs: list[CostPoint]
    changed_vs_mean_price: int
    solve_seconds: float | None = None

class EvaluationResponse(BaseModel):
    context: Literal["TEST evaluation only"] = "TEST evaluation only"
    alpha: float
    exploratory: bool
    schedule: dict[str, int]
    metrics: dict[str, float]
    daily_costs: list[dict]
    sorted_costs: list[CostPoint]
    warning: str
