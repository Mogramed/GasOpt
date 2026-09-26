"""SYNTHETIC fixtures only: they validate plumbing, never empirical savings."""

from dataclasses import replace
from datetime import date
from pathlib import Path
import socket

import numpy as np
import pandas as pd
import pytest

from gasopt.baselines import immediate_schedule
from gasopt.config import ExperimentConfig, load_config
from gasopt.data.dune import import_extract, render_sql
from gasopt.data.empirical import (build_workload, daily_scenarios, load_provenance,
    prepare_local_data, split_daily_slots, validate_daily_slots)
from gasopt.empirical_study import fit_strategies, study_from_frames
from gasopt.evaluation.metrics import scenario_costs_eth
from gasopt.evaluation.out_of_sample import cost_summary, evaluate_schedules, savings
from gasopt.models import solve_deterministic, solve_stochastic
from gasopt.types import OptimizationConfig, Scenario, Transaction


@pytest.fixture
def empirical_fixture():
    """Deterministic 28-day SYNTHETIC schema fixture, not Ethereum observations."""
    config = ExperimentConfig(date(2025, 1, 1), date(2025, 1, 24), date(2025, 1, 25), date(2025, 1, 28),
                              alpha=.8, lambda_grid=(0, .5, 2), min_train_tail_count=1)
    rows, observations = [], []
    for day_index, day in enumerate(pd.date_range(config.train_start, config.test_end, tz="UTC")):
        for slot in range(1, 13):
            price = (10 + (day_index * 7 + slot * 3) % 13 + (20 if day_index % 6 == 0 and slot < 7 else 0)) / 10
            rows.append({"day": day.strftime("%Y-%m-%d"), "slot": slot,
                "slot_start_utc": (day + pd.Timedelta(hours=2 * (slot - 1))).isoformat(),
                "transaction_count": 1000, "valid_transaction_count": 999,
                "median_gas_price_gwei": price, "mean_gas_price_gwei": price * 1.2,
                "p25_gas_price_gwei": price * .8, "p75_gas_price_gwei": price * 1.3,
                "p95_gas_price_gwei": price * 2, "median_gas_used": 45_000,
                "unit_check_count": 999, "unit_check_median_relative_error": 0,
                "unit_check_p95_relative_error": 0})
        if day.date() <= config.train_end:
            for k in range(4):
                number = day_index * 4 + k + 1
                observations.append({"day": day.strftime("%Y-%m-%d"),
                    "block_time_utc": (day + pd.Timedelta(hours=k)).isoformat(),
                    "tx_hash": "0x" + f"{number:064x}", "gas_used": 21_000 + number * 1500})
    return config, pd.DataFrame(rows), pd.DataFrame(observations)


def test_fixed_default_dates_and_grid():
    config = load_config()
    assert (config.train_end - config.train_start).days + 1 == 365
    assert (config.test_end - config.test_start).days + 1 == 90
    assert len(config.lambda_grid) == 11 and max(config.lambda_grid) == 5


@pytest.mark.parametrize("changes", [{"test_start": "2025-01-24"}, {"train_end": "2025-01-29"},
    {"alpha": 1}, {"lambda_grid": (0, 0)}, {"lambda_grid": (-1,)}, {"urgent_window": 13}])
def test_config_rejects_leakage_and_invalid_settings(empirical_fixture, changes):
    config, _, _ = empirical_fixture
    with pytest.raises(ValueError):
        replace(config, **changes)


@pytest.mark.parametrize("release,deadline", [(0, 2), (3, 2), (1.5, 4), (True, 4)])
def test_invalid_release_times(release, deadline):
    with pytest.raises(ValueError):
        Transaction("a", 21_000, deadline, release)


def test_release_and_deadline_constraints():
    txs = (Transaction("a", 21_000, 3, 2), Transaction("b", 40_000, 4, 4))
    scenarios = (Scenario("s1", (1, 9, 5, 10), .5), Scenario("s2", (1, 8, 6, 11), .5))
    assert immediate_schedule(txs) == {"a": 2, "b": 4}
    for solve in (solve_deterministic, solve_stochastic):
        result = solve(txs, scenarios)
        assert result.schedule == {"a": 3, "b": 4}
        assert result.num_binary_variables == 3
        assert result.x_values["a", 1] == result.x_values["b", 3] == 0
    with pytest.raises(ValueError, match="release"):
        scenario_costs_eth(txs, scenarios, {"a": 1, "b": 4})


def test_daily_dimensions_and_split(empirical_fixture):
    config, raw, _ = empirical_fixture
    clean, report = validate_daily_slots(raw, config)
    train, test = split_daily_slots(clean, config)
    scenarios = daily_scenarios(train)
    assert len(scenarios) == 24
    assert all(len(s.prices_gwei) == 12 and s.probability == 1 / 24 for s in scenarios)
    assert train.day.max() < test.day.min()
    assert set(train.day).isdisjoint(test.day)
    assert report["raw_transaction_observations"] == 28 * 12 * 1000
    assert report["excluded_transaction_observations"] == 28 * 12
    assert str(clean.slot_start_utc.dt.tz) == "UTC"


def test_missing_slots_days_and_prices_reported(empirical_fixture):
    config, raw, _ = empirical_fixture
    config = replace(config, max_missing_day_fraction=.3)
    broken = raw.drop(index=0).copy()
    broken = broken.loc[broken.day != "2025-01-02"]
    broken.loc[(broken.day == "2025-01-25") & (broken.slot == 5), "median_gas_price_gwei"] = np.nan
    with pytest.warns(UserWarning, match="removed/absent"):
        clean, report = validate_daily_slots(broken, config)
    assert report["train_dropped_or_absent_days"] == ["2025-01-01", "2025-01-02"]
    assert report["test_dropped_or_absent_days"] == ["2025-01-25"]
    assert clean.groupby("day").size().eq(12).all()
    assert not clean.median_gas_price_gwei.isna().any()
    with pytest.raises(ValueError, match="12 complete"):
        daily_scenarios(raw.drop(index=0))


@pytest.mark.parametrize("defect", ["duplicate", "negative_price", "zero_gas", "naive_time", "wrong_timezone", "slot_alignment", "unit", "unit_coverage"])
def test_data_quality_rejects_corruption(empirical_fixture, defect):
    config, raw, _ = empirical_fixture
    broken = raw.copy()
    if defect == "duplicate":
        broken = pd.concat([broken, broken.iloc[[0]]])
    elif defect == "negative_price":
        broken.loc[0, "median_gas_price_gwei"] = -1
    elif defect == "zero_gas":
        broken.loc[0, "median_gas_used"] = 0
    elif defect == "naive_time":
        broken.loc[0, "slot_start_utc"] = "2025-01-01 00:00:00"
    elif defect == "wrong_timezone":
        broken.loc[0, "slot_start_utc"] = "2025-01-01T00:00:00+02:00"
    elif defect == "slot_alignment":
        broken.loc[0, "slot_start_utc"] = "2025-01-01T01:00:00Z"
    elif defect == "unit":
        broken.loc[0, "unit_check_median_relative_error"] = 1e9 - 1
    else:
        broken.loc[0, "unit_check_count"] = 1
    with pytest.raises(ValueError):
        validate_daily_slots(broken, config)


def test_workload_is_observed_train_only_and_reproducible(empirical_fixture):
    config, _, raw = empirical_fixture
    first, table, info = build_workload(raw, config)
    second, shuffled_table, _ = build_workload(raw.sample(frac=1, random_state=42), config)
    assert first == second and len(first) == 30
    pd.testing.assert_frame_equal(table, shuffled_table)
    assert table.source_tx_hash.is_unique
    observed = raw.set_index("tx_hash").gas_used
    assert all(observed[row.source_tx_hash] == row.gas_used for row in table.itertuples())
    assert table.priority_class.value_counts().to_dict() == {"URGENT": 10, "STANDARD": 10, "FLEXIBLE": 10}
    assert all(1 <= tx.release_slot <= tx.deadline <= 12 for tx in first)
    assert sum(tx.deadline - tx.release_slot + 1 for tx in first) == 140
    contaminated = raw.copy()
    contaminated.loc[0, "day"] = config.test_start.isoformat()
    with pytest.raises(ValueError, match="exclusively from TRAIN"):
        build_workload(contaminated, config)


def test_empirical_equivalence_with_release_times(empirical_fixture):
    config, slots, gas = empirical_fixture
    clean, _ = validate_daily_slots(slots, config)
    train, _ = split_daily_slots(clean, config)
    scenarios = daily_scenarios(train)
    transactions, _, _ = build_workload(gas, config)
    a, b = solve_deterministic(transactions, scenarios), solve_stochastic(transactions, scenarios)
    assert a.expected_cost_eth == pytest.approx(b.expected_cost_eth, abs=1e-10)
    assert a.num_binary_variables == 140


def test_manual_held_out_costs_units_cvar_and_savings():
    txs = (Transaction("a", 21_000, 2, 1), Transaction("b", 50_000, 2, 2))
    test = (Scenario("2025-01-01", (10, 2), .5), Scenario("2025-01-02", (20, 4), .5))
    schedules = {"immediate": {"a": 1, "b": 2}, "optimized": {"a": 2, "b": 2}}
    daily, metrics = evaluate_schedules(txs, test, schedules, .95)
    assert daily.immediate.tolist() == pytest.approx([.00031, .00062])
    assert daily.optimized.tolist() == pytest.approx([.000142, .000284])
    row = metrics.set_index("strategy").loc["optimized"]
    assert row.test_mean_cost_eth == pytest.approx(.000213)
    assert row.test_cvar_eth == pytest.approx(.000284)
    assert row.test_savings_eth == pytest.approx(.000252)
    assert row.test_savings_fraction == pytest.approx(.000252 / .000465)
    assert row.test_savings_percent == pytest.approx(100 * .000252 / .000465)
    assert row.test_p95_cost_eth == row.test_var_eth
    assert row.test_std_cost_eth == pytest.approx(np.std([.000142, .000284]))


def test_fractional_tail_and_savings_convention():
    summary = cost_summary([1, 2, 3, 4, 5], .7)
    assert summary["cvar_eth"] == pytest.approx(14 / 3)
    assert summary["var_eth"] == 4
    assert savings(10, 12)["savings_percent"] == -20
    with pytest.raises(ValueError):
        savings(0, 1)


def test_test_prices_cannot_change_fitted_schedules(empirical_fixture):
    config, slots, gas = empirical_fixture
    clean, _ = validate_daily_slots(slots, config)
    with pytest.warns(UserWarning, match="TEST CVaR"):
        first = study_from_frames(clean, gas, config)
    changed = clean.copy()
    changed.loc[changed.day.dt.date >= config.test_start, "median_gas_price_gwei"] *= 100
    with pytest.warns(UserWarning, match="TEST CVaR"):
        second = study_from_frames(changed, gas, config)
    assert first["fitted"].schedules == second["fitted"].schedules
    pd.testing.assert_frame_equal(first["fitted"].training_metrics, second["fitted"].training_metrics)
    np.testing.assert_allclose(second["test_daily_costs"], first["test_daily_costs"] * 100)
    assert "expected_value_equivalence" not in set(first["test_metrics"].strategy)
    assert first["fitted"].schedules["cvar_lambda_0"] == first["fitted"].schedules["mean_price"]


def test_truncated_workload_export_rejected(empirical_fixture):
    config, _, gas = empirical_fixture
    with pytest.raises(ValueError, match="truncated export"):
        build_workload(gas.iloc[:40], config)


def test_tail_guard_prevents_tiny_training_tail(empirical_fixture):
    config, slots, gas = empirical_fixture
    clean, _ = validate_daily_slots(slots, config)
    train, _ = split_daily_slots(clean, config)
    txs, _, _ = build_workload(gas, config)
    with pytest.warns(UserWarning, match="TRAIN tail"):
        with pytest.raises(ValueError, match="Too few TRAIN"):
            fit_strategies(txs, daily_scenarios(train), replace(config, alpha=.95, min_train_tail_count=10))


def test_query_rendering_is_fixed_and_training_only(empirical_fixture):
    config, _, _ = empirical_fixture
    slots = render_sql(Path("sql/ethereum_gas.sql"), config)
    workload = render_sql(Path("sql/ethereum_workload.sql"), config)
    assert "{{" not in slots + workload
    assert "CURRENT_DATE" not in (slots + workload).upper()
    assert config.test_end.isoformat() in slots
    assert config.test_start.isoformat() not in workload.split("AND block_time <")[0]
    assert "1e-9 AS gas_price_gwei" in slots
    assert "FROM gas.fees" in slots and "blockchain = 'ethereum'" in slots


def test_manual_csv_parquet_import_metadata_and_offline_preparation(empirical_fixture, tmp_path, monkeypatch):
    """Fake Dune provenance is restricted to this temporary synthetic test directory."""
    config, slots, gas = empirical_fixture
    def no_network(*args, **kwargs):
        raise AssertionError("Offline preparation attempted network access")
    monkeypatch.setattr(socket, "create_connection", no_network)
    paths = {}
    for kind, frame, extension in (("slots", slots, ".csv"), ("workload", gas, ".parquet")):
        original = tmp_path / f"SYNTHETIC_fixture_{kind}{extension}"
        archived = tmp_path / "archived" / original.name
        frame.to_csv(original, index=False) if extension == ".csv" else frame.to_parquet(original, index=False)
        query = render_sql(Path("sql") / ("ethereum_gas.sql" if kind == "slots" else "ethereum_workload.sql"), config)
        import_extract(original, archived, query, config, kind, "2026-09-23T12:00:00Z", "SYNTHETIC TEST FIXTURE")
        assert load_provenance(archived, config, kind)["source_reference"] == "SYNTHETIC TEST FIXTURE"
        paths[kind] = archived
    report = prepare_local_data(paths["slots"], paths["workload"], config, tmp_path / "processed")
    assert report["quality"]["retained_daily_scenarios"] == 28
    saved = pd.read_parquet(tmp_path / "processed/ethereum_daily_slots.parquet")
    assert len(saved) == len(slots)
    paths["slots"].write_text(paths["slots"].read_text() + "\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_provenance(paths["slots"], config, "slots")
