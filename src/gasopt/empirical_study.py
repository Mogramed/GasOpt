"""Offline empirical study: train once, freeze schedules, evaluate on later days."""

import argparse
from dataclasses import dataclass
from importlib.metadata import version
import json
from pathlib import Path
import platform
import warnings

import numpy as np
import pandas as pd

from gasopt.baselines import immediate_schedule
from gasopt.config import ExperimentConfig, load_config
from gasopt.data.dune import file_hash
from gasopt.data.empirical import (build_workload, daily_scenarios, prepare_local_data,
                                   read_extract, split_daily_slots)
from gasopt.evaluation.metrics import scenario_costs_eth
from gasopt.evaluation.out_of_sample import cost_summary, evaluate_schedules
from gasopt.models import solve_deterministic, solve_stochastic
from gasopt.types import OptimizationConfig, OptimizationResult, Scenario, Transaction


@dataclass
class FittedStrategies:
    """Training-only outputs; expected-value formulation is pedagogical."""

    schedules: dict[str, dict[str, int]]
    training_metrics: pd.DataFrame
    solver_results: dict[str, OptimizationResult]


def fit_strategies(
    transactions: tuple[Transaction, ...], train: tuple[Scenario, ...], config: ExperimentConfig,
) -> FittedStrategies:
    """Optimize from TRAIN only. This signature deliberately has no TEST input."""
    tail = (1 - config.alpha) * len(train)
    if tail + 1e-12 < config.min_train_tail_count:
        warnings.warn(f"TRAIN tail mass is only {tail:.2f} scenarios.", stacklevel=2)
        raise ValueError("Too few TRAIN tail observations for configured alpha; obtain more data or lower alpha.")
    if any(not config.train_start <= pd.Timestamp(s.id).date() <= config.train_end for s in train):
        raise ValueError("Optimization received a scenario outside TRAIN dates.")
    schedules = {"immediate": immediate_schedule(transactions)}
    results = {}
    base_config = OptimizationConfig(alpha=config.alpha)
    results["mean_price"] = solve_deterministic(transactions, train, base_config)
    results["expected_value_equivalence"] = solve_stochastic(transactions, train, base_config)
    if not np.isclose(results["mean_price"].objective_value_eth,
                      results["expected_value_equivalence"].objective_value_eth, atol=1e-10, rtol=1e-8):
        raise RuntimeError("Mean-price and expected-value objectives disagree.")
    for risk in config.lambda_grid:
        name = f"cvar_lambda_{risk:g}"
        # Use the same risk-neutral representative at zero, so solver tie choices
        # cannot masquerade as an economic difference between equivalent models.
        results[name] = results["mean_price"] if risk == 0 else solve_stochastic(
            transactions, train, OptimizationConfig(alpha=config.alpha, lambda_risk=risk))
    schedules.update({name: result.schedule.copy() for name, result in results.items()})
    rows = []
    for name, schedule in schedules.items():
        metrics = cost_summary(list(scenario_costs_eth(transactions, train, schedule).values()), config.alpha)
        row = {"strategy": name, "lambda_risk": float(name.removeprefix("cvar_lambda_")) if name.startswith("cvar_") else 0.0,
               "train_expected_cost_eth": metrics["mean_cost_eth"], "train_var_eth": metrics["var_eth"],
               "train_cvar_eth": metrics["cvar_eth"], "train_worst_cost_eth": metrics["max_cost_eth"],
               "train_tail_scenario_count": tail, "schedule": json.dumps(schedule, sort_keys=True),
               "role": "pedagogical equivalence only" if name == "expected_value_equivalence" else "evaluation strategy"}
        result = results.get(name)
        row.update({"objective_value_eth": result.objective_value_eth if result else metrics["mean_cost_eth"],
                    "solver_status": result.solver_status if result else "not_applicable_baseline",
                    "optimality_gap": result.optimality_gap if result else None,
                    "objective_bound_eth": result.objective_bound_eth if result else None,
                    "num_variables": result.num_variables if result else 0,
                    "num_binary_variables": result.num_binary_variables if result else 0,
                    "num_constraints": result.num_constraints if result else 0,
                    "node_count": result.node_count if result else None})
        rows.append(row)
    return FittedStrategies(schedules, pd.DataFrame(rows), results)


def load_processed(directory: Path, config: ExperimentConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load and verify saved processed data, entirely offline."""
    meta_path = directory / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError("No verified empirical dataset. Run the prepare command after Dune extraction.")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if metadata.get("data_kind") != "empirical":
        raise ValueError("Scientific run requires empirical provenance, not a test fixture.")
    for name, digest in metadata["processed_hashes"].items():
        if file_hash(directory / name) != digest:
            raise ValueError(f"Processed data hash mismatch: {name}")
    # Lambda and alpha may change without re-extracting. Dates and workload rules
    # must match the saved dataset; a new preparation records deliberate changes.
    settings = config.to_dict()
    reusable = {"alpha", "lambda_grid", "min_train_tail_count"}
    if any(metadata["config"].get(key) != value for key, value in settings.items() if key not in reusable):
        raise ValueError("Prepared data/config mismatch. Re-run prepare from matching archived extracts.")
    return (read_extract(directory / "ethereum_daily_slots.parquet"),
            read_extract(directory / "ethereum_workload_observations.parquet"), metadata)


def study_from_frames(
    slots: pd.DataFrame, workload_observations: pd.DataFrame, config: ExperimentConfig,
) -> dict:
    """Core computation on validated frames, also exercisable with labelled test fixtures."""
    train_slots, test_slots = split_daily_slots(slots, config)
    train, test = daily_scenarios(train_slots), daily_scenarios(test_slots)
    transactions, workload, construction = build_workload(workload_observations, config)
    fitted = fit_strategies(transactions, train, config)
    # B and C have one economic interpretation; C is not separately ranked on TEST.
    evaluated = {name: schedule.copy() for name, schedule in fitted.schedules.items()
                 if name != "expected_value_equivalence"}
    test_costs, test_metrics = evaluate_schedules(transactions, test, evaluated, config.alpha)
    test_tail = (1 - config.alpha) * len(test)
    if test_tail < 10:
        warnings.warn(f"TEST CVaR tail has only {test_tail:.2f} scenario equivalents; interpret cautiously.", stacklevel=2)
    schedule_rows = [{"strategy": name, "transaction_id": tx.id, "slot": schedule[tx.id]}
                     for name, schedule in fitted.schedules.items() for tx in transactions]
    return {"fitted": fitted, "transactions": transactions, "workload": workload,
            "workload_construction": construction, "train_slots": train_slots, "test_slots": test_slots,
            "test_daily_costs": test_costs, "test_metrics": test_metrics,
            "schedules": pd.DataFrame(schedule_rows), "train_count": len(train), "test_count": len(test)}


def run_study(config: ExperimentConfig, processed: Path, output: Path) -> dict:
    """Produce auditable empirical tables, model diagnostics and plots offline."""
    slots, workload_observations, metadata = load_processed(processed, config)
    study = study_from_frames(slots, workload_observations, config)
    output.mkdir(parents=True, exist_ok=True)
    tables = {"train_metrics.csv": study["fitted"].training_metrics,
              "test_metrics.csv": study["test_metrics"], "schedules.csv": study["schedules"],
              "treasury_workload.csv": study["workload"]}
    for name, frame in tables.items():
        frame.to_csv(output / name, index=False)
    study["test_daily_costs"].to_csv(output / "test_daily_costs.csv")
    study["test_daily_costs"].to_parquet(output / "test_daily_costs.parquet")
    comparison = study["fitted"].training_metrics.merge(study["test_metrics"], on="strategy", how="inner")
    comparison.to_csv(output / "strategy_comparison.csv", index=False)
    report = {"data_kind": "empirical", "source": metadata["source"], "config": config.to_dict(),
              "source_references": {name: details["source_reference"] for name, details in
                                    metadata["provenance"].items()},
              "data_quality": metadata["quality"], "workload_construction": study["workload_construction"],
              "retained_train_days": study["train_count"], "retained_test_days": study["test_count"],
              "train_tail_count": (1 - config.alpha) * study["train_count"],
              "test_tail_count": (1 - config.alpha) * study["test_count"],
              "test_role": "evaluation only; no lambda selection or refitting",
              "p95_method": "inverse empirical CDF", "std_ddof": 0,
              "processed_metadata_sha256": file_hash(processed / "metadata.json"),
              "environment": {"python": platform.python_version(), **{name: version(name) for name in
                              ("gasopt", "pyomo", "highspy", "numpy", "pandas", "pyarrow", "matplotlib")}},
              "schedules": study["fitted"].schedules}
    (output / "study_metadata.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    from gasopt.plots import save_study_plots
    save_study_plots(slots, workload_observations, study, config, output / "plots", label="EMPIRICAL ETHEREUM")
    write_report(study, report, output / "report.md")
    return study


def write_report(study: dict, metadata: dict, path: Path) -> None:
    """Generate a self-contained numerical report without selecting lambda on TEST."""
    config = metadata["config"]
    quality = metadata["data_quality"]
    workload = metadata["workload_construction"]
    references = metadata.get("source_references", {})
    lines = ["# GasOpt empirical study", "", "Source: Dune Analytics `gas.fees`, Ethereum Mainnet.",
             f"TRAIN: {config['train_start']} to {config['train_end']} (inclusive UTC).",
             f"TEST: {config['test_start']} to {config['test_end']} (inclusive UTC).", "",
             f"Retained scenarios: {study['train_count']} TRAIN; {study['test_count']} TEST.",
             f"Tail scenario equivalents: {metadata['train_tail_count']:.2f} TRAIN; {metadata['test_tail_count']:.2f} TEST.",
             "", "## Data and provenance", "",
             f"- Dune slot execution: `{references.get('slots', 'see processed metadata')}`",
             f"- Dune workload execution: `{references.get('workload', 'see processed metadata')}`",
             f"- Aggregated day-slot rows: {quality['retained_aggregate_rows']:,}",
             f"- Underlying source transactions: {quality['raw_transaction_observations']:,}",
             f"- Excluded source transactions: {quality['excluded_transaction_observations']:,}",
             f"- Missing or incomplete retained days: "
             f"{len(quality['train_dropped_or_absent_days']) + len(quality['test_dropped_or_absent_days'])}",
             f"- TRAIN workload observations: {workload['raw_sample_rows']:,}; "
             f"selected actual observations: {workload['transaction_count']}",
             "- Interpolation: none; winsorization: none", "",
             "## Training diagnostics", "",
             "| Strategy | Lambda | Expected ETH | CVaR ETH | Worst ETH | Objective ETH | Status |",
             "|:--|--:|--:|--:|--:|--:|:--|"]
    for row in study["fitted"].training_metrics.itertuples(index=False):
        lines.append(f"| {row.strategy} | {row.lambda_risk:g} | {row.train_expected_cost_eth:.9f} | "
                     f"{row.train_cvar_eth:.9f} | {row.train_worst_cost_eth:.9f} | "
                     f"{row.objective_value_eth:.9f} | {row.solver_status} |")
    lines.extend(["", "## Frozen schedules", "",
                  "Slots are one-based and ordered from `treasury_01` through `treasury_30`.", "",
                  "| Strategy | Assigned slots |", "|:--|:--|"])
    for strategy, schedule in study["fitted"].schedules.items():
        slots = ",".join(str(slot) for slot in schedule.values())
        lines.append(f"| {strategy} | `({slots})` |")
    lines.extend(["", "## Out-of-sample comparison", "",
             "| Strategy | Mean ETH | CVaR ETH | Worst ETH | Savings ETH | Savings % |",
             "|:--|--:|--:|--:|--:|--:|"])
    for row in study["test_metrics"].itertuples(index=False):
        lines.append(f"| {row.strategy} | {row.test_mean_cost_eth:.9f} | {row.test_cvar_eth:.9f} | "
                     f"{row.test_max_cost_eth:.9f} | {row.test_savings_eth:.9f} | {row.test_savings_percent:.3f} |")
    unique = len({tuple(s.values()) for n, s in study["fitted"].schedules.items() if n.startswith("cvar_")})
    lines.extend(["", f"Distinct CVaR schedules across the prespecified grid: {unique}.",
                  "Mean-price and expected-value objectives agree; C is a pedagogical equivalence check.",
                  "No risk weight is selected using TEST performance. See train_metrics.csv for objectives, "
                  "VaR/CVaR, solver status, bounds and model dimensions; schedules.csv contains every assignment.",
                  "", "## Limits", "", "Slot medians are execution-price proxies, not attainable-price guarantees. "
                  "Timing classes are business assumptions. Serial dependence, regime changes, gas-use uncertainty, "
                  "nonce constraints and inclusion uncertainty remain outside the model. "
                  "The small TEST tail limits precision; no statistical significance is claimed."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Separate offline preparation from offline model fitting and reporting."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--config", type=Path, default=Path("config/empirical.toml"))
    parser.add_argument("--slots", type=Path, default=Path("data/raw/ethereum_slots.csv"))
    parser.add_argument("--workload", type=Path, default=Path("data/raw/ethereum_workload.csv"))
    parser.add_argument("--processed", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("outputs/empirical"))
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "prepare":
        metadata = prepare_local_data(args.slots, args.workload, config, args.processed)
        print(json.dumps(metadata["quality"], indent=2))
    else:
        result = run_study(config, args.processed, args.output)
        print(result["test_metrics"].to_string(index=False))


if __name__ == "__main__":
    main()
