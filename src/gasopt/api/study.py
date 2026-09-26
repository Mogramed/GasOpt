"""Immutable local study snapshot and presentation adapters; never writes artifacts."""
from pathlib import Path
from hashlib import sha256
import json
from math import isclose
import numpy as np
import pandas as pd
from gasopt.config import load_config
from gasopt.empirical_study import load_processed
from gasopt.data.empirical import build_workload, split_daily_slots, daily_scenarios
from gasopt.data.dune import file_hash
from gasopt.evaluation.metrics import scenario_costs_eth, mean_prices_gwei
from gasopt.evaluation.out_of_sample import cost_summary, evaluate_schedules
from gasopt.baselines import immediate_schedule
from gasopt.api.serialization import records, schedule_id, cost_points, utc_range
from gasopt.api.optimization import TrainingOptimizer
from gasopt.api.evaluation import evaluate_frozen

class Study:
    def __init__(self, root: Path):
        self.root = root
        self.config = load_config(root / "config/empirical.toml")
        self.slots, self.observations, self.metadata = load_processed(root / "data/processed", self.config)
        self.transactions, self.workload, self.construction = build_workload(self.observations, self.config)
        train_slots, test_slots = split_daily_slots(self.slots, self.config)
        self.frames = {"TRAIN": train_slots, "TEST": test_slots, "ALL": self.slots}
        self.train, self.test = daily_scenarios(train_slots), daily_scenarios(test_slots)
        self.means = mean_prices_gwei(self.train)
        out = root / "outputs/empirical"
        self.archive_meta = json.loads((out / "study_metadata.json").read_text())
        if self.archive_meta["processed_metadata_sha256"] != file_hash(root / "data/processed/metadata.json"):
            raise ValueError("Archived study and processed data identities differ.")
        if self.archive_meta["config"] != json.loads(json.dumps(self.config.to_dict())):
            raise ValueError("Archived study/config mismatch.")
        self.train_table = pd.read_csv(out / "train_metrics.csv")
        self.test_table = pd.read_csv(out / "test_metrics.csv")
        self.daily_test = pd.read_csv(out / "test_daily_costs.csv")
        self.schedules = {r.strategy: json.loads(r.schedule) for r in self.train_table.itertuples()}
        self.dataset_id = sha256((file_hash(root / "data/processed/metadata.json") +
                                 file_hash(out / "study_metadata.json")).encode()).hexdigest()[:16]
        self._audit_archive()
        self.optimizer = TrainingOptimizer(self.transactions, self.train, self.config, self.dataset_id)

    def _audit_archive(self):
        """Verify displayed archived metrics against the same core, without solving."""
        for row in self.train_table.itertuples():
            costs = scenario_costs_eth(self.transactions, self.train, self.schedules[row.strategy])
            metric = cost_summary(list(costs.values()), self.config.alpha)
            for field, key in (("train_expected_cost_eth", "mean_cost_eth"), ("train_var_eth", "var_eth"),
                               ("train_cvar_eth", "cvar_eth"), ("train_worst_cost_eth", "max_cost_eth")):
                if not isclose(getattr(row, field), metric[key], rel_tol=1e-9, abs_tol=1e-12):
                    raise ValueError(f"Archived TRAIN metric mismatch: {row.strategy}/{field}")
        evaluated = {k: v for k, v in self.schedules.items() if k != "expected_value_equivalence"}
        daily, metrics = evaluate_schedules(self.transactions, self.test, evaluated, self.config.alpha)
        expected = metrics.set_index("strategy").sort_index()
        saved = self.test_table.set_index("strategy").sort_index()
        if list(expected.index) != list(saved.index) or not np.allclose(expected, saved[expected.columns], rtol=1e-9, atol=1e-12):
            raise ValueError("Archived TEST metrics do not match frozen evaluation.")
        if self.daily_test.test_day.tolist() != list(daily.index) or not np.allclose(
                self.daily_test[daily.columns], daily, rtol=1e-9, atol=1e-12):
            raise ValueError("Archived daily TEST costs do not match frozen evaluation.")
        if self.schedules != self.archive_meta["schedules"]:
            raise ValueError("Archived schedules disagree across artifacts.")

    def meta(self):
        return {"product": "GasOps", "dataset_id": self.dataset_id, "config": self.config.to_dict(),
                "quality": self.metadata["quality"], "source": self.metadata["source"],
                "provenance": self.metadata["provenance"], "construction": self.construction,
                "train_days": len(self.train), "test_days": len(self.test),
                "transaction_count": len(self.transactions), "slots": len(self.train[0].prices_gwei),
                "binary_decisions": int(self.train_table.set_index('strategy').loc['mean_price', 'num_binary_variables']),
                "alpha": self.config.alpha, "train_tail_count": (1-self.config.alpha)*len(self.train),
                "test_tail_count": (1-self.config.alpha)*len(self.test), "offline": True}

    def workload_rows(self):
        rows = records(self.workload)
        for row in rows:
            row["window_length"] = row["deadline_slot"] - row["release_slot"] + 1
            row["allowed_slots"] = list(range(row["release_slot"], row["deadline_slot"]+1))
        return rows

    def profile(self):
        frame = self.frames["TRAIN"]
        return [{"slot": slot, "utc_range": utc_range(slot), "mean_gwei": self.means[slot-1],
                 "median_gwei": float(group.median_gas_price_gwei.median()),
                 "p25_gwei": float(group.median_gas_price_gwei.quantile(.25)),
                 "p75_gwei": float(group.median_gas_price_gwei.quantile(.75))}
                for slot, group in frame.groupby("slot")]

    def heatmap(self, split="TRAIN"):
        scenarios = self.train if split == "TRAIN" else self.test
        return {"split": split, "dates": [s.id for s in scenarios],
                "slots": [{"slot": n, "utc_range": utc_range(n)} for n in range(1, 13)],
                "prices": [s.prices_gwei for s in scenarios], "unit": "gwei / gas"}

    def gas_used(self):
        counts, edges = np.histogram(self.observations.gas_used, bins=40)
        return {"sample_count": len(self.observations), "bins": [
            {"lower": float(edges[i]), "upper": float(edges[i+1]), "count": int(count)}
            for i, count in enumerate(counts)], "selected": self.workload_rows(),
            "construction": self.construction}

    def archive(self, strategy):
        if strategy not in self.schedules:
            raise KeyError("Unknown archived strategy.")
        row = self.train_table.set_index("strategy").loc[strategy]
        risk = float(row.lambda_risk)
        data = {"expected_cost_eth": float(row.train_expected_cost_eth), "var_eth": float(row.train_var_eth),
                "cvar_eth": float(row.train_cvar_eth), "worst_case_cost_eth": float(row.train_worst_cost_eth),
                "objective_value_eth": float(row.objective_value_eth), "solver_status": row.solver_status,
                **{key: None if pd.isna(row[key]) else float(row[key]) for key in
                   ("objective_bound_eth", "optimality_gap")},
                **{key: int(row[key]) for key in ("num_variables", "num_binary_variables", "num_constraints")}}
        return self._result(self.schedules[strategy], risk, self.config.alpha, data, "archived", strategy)

    def _result(self, schedule, risk, alpha, data, origin, strategy, duration=None):
        costs = scenario_costs_eth(self.transactions, self.train, schedule)
        return {**data, "origin": origin, "dataset_id": self.dataset_id, "strategy": strategy,
                "schedule_id": schedule_id(schedule), "schedule": schedule.copy(),
                "lambda_risk": risk, "alpha": alpha,
                "exploratory": risk not in self.config.lambda_grid or alpha != self.config.alpha,
                "tail_scenario_count": (1-alpha)*len(self.train), "node_count": None,
                "assignments": [{"transaction_id": tx.id, "slot": schedule[tx.id]} for tx in self.transactions],
                "scenario_costs": cost_points(costs, alpha),
                "changed_vs_mean_price": sum(schedule[k] != v for k, v in self.schedules["mean_price"].items()),
                "solve_seconds": duration}

    def solve(self, risk, alpha):
        r, origin, duration = self.optimizer.solve(risk, alpha)
        data = {key: getattr(r, key) for key in ("expected_cost_eth", "cvar_eth", "worst_case_cost_eth",
            "objective_value_eth", "solver_status", "objective_bound_eth", "optimality_gap",
            "num_variables", "num_binary_variables", "num_constraints")}
        data["var_eth"] = r.eta_eth
        return self._result(r.schedule, risk, alpha, data, origin, f"live_lambda_{risk:g}", duration)

    def is_exploratory(self, schedule, alpha):
        return alpha != self.config.alpha or schedule not in self.schedules.values()

    def evaluate(self, schedule, alpha):
        return evaluate_frozen(self.transactions, self.test, schedule, alpha, self.is_exploratory(schedule, alpha))

    def compare(self, a, b, alpha):
        ca = scenario_costs_eth(self.transactions, self.train, a)
        cb = scenario_costs_eth(self.transactions, self.train, b)
        ma, mb = cost_summary(list(ca.values()), alpha), cost_summary(list(cb.values()), alpha)
        changed = [{**row, "slot_a": a[row['transaction_id']], "slot_b": b[row['transaction_id']],
                    "slot_difference": b[row['transaction_id']] - a[row['transaction_id']],
                    "mean_price_a": self.means[a[row['transaction_id']]-1],
                    "mean_price_b": self.means[b[row['transaction_id']]-1]}
                   for row in self.workload_rows() if a[row['transaction_id']] != b[row['transaction_id']]]
        return {"changed": changed, "changed_count": len(changed), "metrics_a": ma, "metrics_b": mb,
                "delta_mean_eth": mb['mean_cost_eth']-ma['mean_cost_eth'],
                "delta_cvar_eth": mb['cvar_eth']-ma['cvar_eth'],
                "delta_worst_eth": mb['max_cost_eth']-ma['max_cost_eth'],
                "scenario_differences": [{"date": day, "cost_a": ca[day], "cost_b": cb[day],
                                          "difference_eth": cb[day]-ca[day]} for day in ca]}

    def scenario(self, schedule, split, day, selector, alpha):
        scenarios = self.train if split == "TRAIN" else self.test
        costs = scenario_costs_eth(self.transactions, scenarios, schedule)
        ordered = sorted(costs, key=costs.get)
        if not day:
            day = ordered[{'typical': len(ordered)//2, 'high': int(.95*(len(ordered)-1)), 'worst': len(ordered)-1}[selector]]
        selected = next((s for s in scenarios if s.id == day), None)
        if selected is None:
            raise ValueError("Date does not belong to the selected split.")
        baseline = scenario_costs_eth(self.transactions, scenarios, immediate_schedule(self.transactions))
        mean = scenario_costs_eth(self.transactions, scenarios, self.schedules['mean_price'])
        return {"split": split, "date": day, "schedule": schedule, "selected_cost_eth": costs[day],
                "immediate_cost_eth": baseline[day], "mean_price_cost_eth": mean[day],
                "path": [{"slot": i+1, "gas_price_gwei": p, "utc_range": utc_range(i+1)}
                         for i, p in enumerate(selected.prices_gwei)]}

    def calculator(self, transaction_id, day, slot):
        tx = next((x for x in self.transactions if x.id == transaction_id), None)
        scenario = next((x for x in self.train if x.id == day), None)
        if tx is None or scenario is None:
            raise ValueError("Choose a known transaction and TRAIN day.")
        from gasopt.types import Scenario
        single = Scenario(scenario.id, scenario.prices_gwei, 1.0)
        cost = scenario_costs_eth((tx,), (single,), {tx.id: slot})[day]
        return {"gas_used": tx.gas_used, "gas_price_gwei": scenario.prices_gwei[slot-1],
                "conversion": 1e-9, "cost_eth": cost, "day": day, "slot": slot}

    def sensitivity(self):
        rows = records(self.train_table.loc[self.train_table.strategy.str.startswith('cvar_')])
        for row in rows:
            row['schedule_id'] = schedule_id(self.schedules[row['strategy']])
            row.pop('schedule')
        return rows
