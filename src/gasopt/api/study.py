"""Immutable local study snapshot and presentation adapters; never writes artifacts."""
from pathlib import Path
from hashlib import sha256
import json
from math import isclose
import numpy as np
import pandas as pd
from gasopt.config import load_config
from gasopt.data.processed import json_hash, load_processed
from gasopt.data.empirical import build_workload, split_daily_slots, daily_scenarios
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
        processed_identity = json_hash(root / "data/processed/metadata.json")
        if self.archive_meta["processed_metadata_sha256"] != processed_identity:
            raise ValueError("Archived study and processed data identities differ.")
        if self.archive_meta["config"] != json.loads(json.dumps(self.config.to_dict())):
            raise ValueError("Archived study/config mismatch.")
        self.train_table = pd.read_csv(out / "train_metrics.csv")
        self.test_table = pd.read_csv(out / "test_metrics.csv")
        self.daily_test = pd.read_csv(out / "test_daily_costs.csv")
        self.schedules = {r.strategy: json.loads(r.schedule) for r in self.train_table.itertuples()}
        self.dataset_id = sha256(
            (processed_identity + json_hash(out / "study_metadata.json")).encode()
        ).hexdigest()[:16]
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

    def _result(self, schedule, risk, alpha, data, origin, strategy, duration=None,
                solver_eta=None, solver_cvar=None):
        costs = scenario_costs_eth(self.transactions, self.train, schedule)
        result_id = schedule_id(schedule)
        points = cost_points(costs, alpha)
        eta = float(data["var_eth"])
        cvar = float(data["cvar_eth"])
        weighted_excess = sum(point["probability"] * point["xi_eth"] for point in points)
        example_tx = self.transactions[0]
        worst_day = max(costs, key=costs.get)
        worst_scenario = next(s for s in self.train if s.id == worst_day)
        example_slot = schedule[example_tx.id]
        example_price = worst_scenario.prices_gwei[example_slot - 1]
        example_cost = 1e-9 * example_tx.gas_used * example_price
        changed = sum(schedule[k] != v for k, v in self.schedules["mean_price"].items())
        binaries = int(data["num_binary_variables"])
        variables = int(data["num_variables"])
        constraints = int(data["num_constraints"])
        node_count = data.get("node_count")
        objective_residual = float(data["objective_value_eth"]) - (
            float(data["expected_cost_eth"]) + risk * cvar)
        solver_method = {
            "name": "HiGHS mixed-integer optimizer",
            "version": data.get("highs_version"),
            "problem_class": "MILP",
            "algorithm": "Presolve + LP relaxations + Branch-and-Bound",
            "lp_engine": "automatic HiGHS selection",
            "presolve": "automatic",
            "threads": 1,
            "random_seed": 0,
            "relative_gap_tolerance": 0.0,
            "absolute_gap_tolerance": 1e-10,
            "mip_feasibility_tolerance": 1e-9,
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
        }
        simplex_iterations = data.get("simplex_iteration_count")
        ipm_iterations = data.get("ipm_iteration_count")
        simplex_label = str(simplex_iterations) if simplex_iterations is not None else "not reported"
        ipm_label = str(ipm_iterations) if ipm_iterations is not None else "not used / not reported"
        solver_stages = [
            {"step": 1, "label": "Validate inputs", "status": "passed", "observed": True,
             "mathematics": "q_s >= 0, sum(q_s) = 1; r_i <= d_i",
             "output": f"{len(self.transactions)} transactions, {len(self.train)} scenarios, alpha={alpha:g}, lambda={risk:g}"},
            {"step": 2, "label": "Assemble the MILP", "status": "built", "observed": True,
             "mathematics": "min c^T z subject to A_eq z = 1, A_ub z <= b, x binary",
             "output": f"{variables} variables ({binaries} binary), {constraints} constraints"},
            {"step": 3, "label": "Presolve", "status": "automatic", "observed": False,
             "mathematics": "remove fixed/redundant rows and tighten variable bounds",
             "output": "HiGHS presolve enabled; individual reductions are not exposed by this API response"},
            {"step": 4, "label": "Solve LP relaxation", "status": "completed", "observed": True,
             "mathematics": "replace x_it in {0,1} by 0 <= x_it <= 1 to obtain a lower bound",
             "output": f"simplex iterations={simplex_label}, IPM iterations={ipm_label}"},
            {"step": 5, "label": "Run MIP heuristics and cuts", "status": "internal", "observed": False,
             "mathematics": "strengthen the relaxation and search for integer-feasible incumbents",
             "output": "Managed internally by HiGHS; per-cut and per-heuristic events are not exposed"},
            {"step": 6, "label": "Branch-and-Bound", "status": "completed", "observed": True,
             "mathematics": "maintain LB <= f* <= UB and branch only while the gap remains open",
             "output": (f"closed at the root; reported node count={node_count}"
                        if node_count is not None and node_count <= 1
                        else f"reported node count={node_count}")},
            {"step": 7, "label": "Close the optimality gap", "status": data["solver_status"], "observed": True,
             "mathematics": "gap = |UB - LB| / max(1, |UB|)",
             "output": f"incumbent={data['objective_value_eth']:.12g}, bound={data.get('objective_bound_eth')}, gap={data.get('optimality_gap')}"},
            {"step": 8, "label": "Recover the integer schedule", "status": "passed", "observed": True,
             "mathematics": "for each i, exactly one x_it = 1",
             "output": f"{len(schedule)} assignments, schedule {result_id}"},
            {"step": 9, "label": "Independent numerical audit", "status": "passed", "observed": True,
             "mathematics": "recompute C_s, E[C], VaR, CVaR and E[C] + lambda CVaR outside HiGHS",
             "output": f"objective residual={objective_residual:.3e} ETH"},
        ]
        trace = {
            "inputs": {
                "dataset_id": self.dataset_id,
                "transactions": len(self.transactions),
                "train_scenarios": len(self.train),
                "slots": len(self.train[0].prices_gwei),
                "lambda_risk": risk,
                "alpha": alpha,
                "scenario_probability": self.train[0].probability,
                "tail_scenario_equivalents": (1 - alpha) * len(self.train),
            },
            "model": {
                "binary_variables": binaries,
                "continuous_variables": variables - binaries,
                "total_variables": variables,
                "assignment_constraints": len(self.transactions),
                "excess_constraints": constraints - len(self.transactions),
                "total_constraints": constraints,
            },
            "coefficient_example": {
                "transaction_id": example_tx.id,
                "scenario_date": worst_day,
                "selected_slot": example_slot,
                "gas_used": example_tx.gas_used,
                "gas_price_gwei": example_price,
                "conversion": 1e-9,
                "coefficient_eth": example_cost,
                "portfolio_cost_eth": costs[worst_day],
            },
            "risk": {
                "in_objective": risk > 0,
                "eta_eth": eta,
                "solver_eta_eth": solver_eta,
                "tail_multiplier": 1 / (1 - alpha),
                "positive_excess_scenarios": sum(point["xi_eth"] > 0 for point in points),
                "weighted_excess_eth": weighted_excess,
                "cvar_eth": cvar,
                "solver_cvar_eth": solver_cvar,
            },
            "objective": {
                "expected_cost_eth": float(data["expected_cost_eth"]),
                "risk_penalty_eth": risk * cvar,
                "objective_value_eth": float(data["objective_value_eth"]),
            },
            "solver": {
                "status": data["solver_status"],
                "objective_bound_eth": data.get("objective_bound_eth"),
                "optimality_gap": data.get("optimality_gap"),
                "node_count": node_count,
                "solve_seconds": duration,
                "origin": origin,
                "method": solver_method,
                "telemetry": {
                    "simplex_iteration_count": data.get("simplex_iteration_count"),
                    "ipm_iteration_count": data.get("ipm_iteration_count"),
                    "max_primal_infeasibility": data.get("max_primal_infeasibility"),
                    "max_dual_infeasibility": data.get("max_dual_infeasibility"),
                    "max_integrality_violation": data.get("max_integrality_violation"),
                    "objective_audit_residual_eth": objective_residual,
                },
                "stages": solver_stages,
            },
            "solution": {
                "assignment_count": len(schedule),
                "schedule_id": result_id,
                "changed_vs_mean_price": changed,
            },
        }
        return {**data, "origin": origin, "dataset_id": self.dataset_id, "strategy": strategy,
                "schedule_id": result_id, "schedule": schedule.copy(),
                "lambda_risk": risk, "alpha": alpha,
                "exploratory": risk not in self.config.lambda_grid or alpha != self.config.alpha,
                "tail_scenario_count": (1-alpha)*len(self.train), "node_count": node_count,
                "assignments": [{"transaction_id": tx.id, "slot": schedule[tx.id]} for tx in self.transactions],
                "scenario_costs": points, "changed_vs_mean_price": changed,
                "solve_seconds": duration, "calculation_trace": trace}

    def solve(self, risk, alpha, force_recompute=False):
        r, origin, duration = self.optimizer.solve(risk, alpha, force_recompute)
        data = {key: getattr(r, key) for key in ("expected_cost_eth", "cvar_eth", "worst_case_cost_eth",
            "objective_value_eth", "solver_status", "objective_bound_eth", "optimality_gap",
            "num_variables", "num_binary_variables", "num_constraints", "node_count",
            "highs_version", "simplex_iteration_count", "ipm_iteration_count",
            "max_primal_infeasibility", "max_dual_infeasibility", "max_integrality_violation")}
        data["var_eth"] = r.eta_eth
        return self._result(r.schedule, risk, alpha, data, origin, f"live_lambda_{risk:g}", duration,
                            r.solver_eta_eth, r.solver_cvar_eth)

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

    def decision_trace(self, schedule, transaction_id, risk, alpha):
        """Explain one decision with exact one-slot counterfactual portfolio metrics.

        The other transactions remain fixed. This gives an interpretable local
        comparison without pretending that portfolio CVaR is transaction-additive.
        """
        tx = next((item for item in self.transactions if item.id == transaction_id), None)
        if tx is None:
            raise ValueError("Choose a known transaction.")
        base_costs = scenario_costs_eth(self.transactions, self.train, schedule)
        selected_slot = schedule[tx.id]
        allowed_slots = list(range(tx.release_slot, tx.deadline + 1))
        if selected_slot not in allowed_slots:
            raise ValueError("The selected schedule violates the transaction window.")

        rows = []
        costs_by_slot = {}
        for slot in allowed_slots:
            candidate = schedule.copy()
            candidate[tx.id] = slot
            costs = scenario_costs_eth(self.transactions, self.train, candidate)
            costs_by_slot[slot] = costs
            metrics = cost_summary(list(costs.values()), alpha)
            tx_expected = 1e-9 * tx.gas_used * self.means[slot - 1]
            rows.append({
                "slot": slot,
                "utc_range": utc_range(slot),
                "selected": slot == selected_slot,
                "mean_gas_price_gwei": self.means[slot - 1],
                "transaction_expected_cost_eth": tx_expected,
                "portfolio_expected_cost_eth": metrics["mean_cost_eth"],
                "portfolio_var_eth": metrics["var_eth"],
                "portfolio_cvar_eth": metrics["cvar_eth"],
                "portfolio_worst_cost_eth": metrics["max_cost_eth"],
                "portfolio_objective_eth": metrics["mean_cost_eth"] + risk * metrics["cvar_eth"],
            })

        selected = next(row for row in rows if row["selected"])
        for row in rows:
            row["delta_objective_eth"] = row["portfolio_objective_eth"] - selected["portfolio_objective_eth"]
        ranked = sorted(rows, key=lambda row: (row["portfolio_objective_eth"], row["slot"]))
        for rank, row in enumerate(ranked, 1):
            row["objective_rank"] = rank
        alternatives = [row for row in ranked if not row["selected"]]
        best_alternative = alternatives[0] if alternatives else None

        comparison_slot = best_alternative["slot"] if best_alternative else selected_slot
        comparison_costs = costs_by_slot[comparison_slot]
        selected_points = {point["date"]: point for point in cost_points(base_costs, alpha)}
        alternative_points = {point["date"]: point for point in cost_points(comparison_costs, alpha)}
        scenario_outputs = [{
            "date": scenario.id,
            "selected_cost_eth": base_costs[scenario.id],
            "alternative_cost_eth": comparison_costs[scenario.id],
            "difference_eth": comparison_costs[scenario.id] - base_costs[scenario.id],
            "selected_tail_mass": selected_points[scenario.id]["tail_mass"],
            "alternative_tail_mass": alternative_points[scenario.id]["tail_mass"],
        } for scenario in self.train]
        worked = max(scenario_outputs, key=lambda row: abs(row["difference_eth"]))
        worked_scenario = next(item for item in self.train if item.id == worked["date"])
        selected_price = worked_scenario.prices_gwei[selected_slot - 1]
        alternative_price = worked_scenario.prices_gwei[comparison_slot - 1]

        return {
            "transaction": {
                "transaction_id": tx.id,
                "gas_used": tx.gas_used,
                "priority_class": tx.priority_class,
                "release_slot": tx.release_slot,
                "deadline_slot": tx.deadline,
                "allowed_slots": allowed_slots,
                "selected_slot": selected_slot,
            },
            "settings": {
                "lambda_risk": risk,
                "alpha": alpha,
                "train_scenarios": len(self.train),
                "fixed_other_transactions": len(self.transactions) - 1,
            },
            "slot_outputs": sorted(rows, key=lambda row: row["slot"]),
            "selected_output": selected,
            "best_alternative": best_alternative,
            "worked_scenario": {
                **worked,
                "selected_slot": selected_slot,
                "alternative_slot": comparison_slot,
                "selected_price_gwei": selected_price,
                "alternative_price_gwei": alternative_price,
                "selected_transaction_cost_eth": 1e-9 * tx.gas_used * selected_price,
                "alternative_transaction_cost_eth": 1e-9 * tx.gas_used * alternative_price,
            },
            "scenario_outputs": scenario_outputs,
            "optimality_check": {
                "selected_is_best_one_move": all(
                    row["delta_objective_eth"] >= -1e-10 for row in rows),
                "smallest_alternative_delta_eth": (
                    best_alternative["delta_objective_eth"] if best_alternative else None),
                "scope": "One-transaction counterfactual; the HiGHS certificate establishes global optimality.",
                "cvar_is_joint": True,
            },
        }

    def sensitivity(self):
        rows = records(self.train_table.loc[self.train_table.strategy.str.startswith('cvar_')])
        for row in rows:
            row['schedule_id'] = schedule_id(self.schedules[row['strategy']])
            row.pop('schedule')
        return rows
