"""Validate local Dune extracts and construct whole-day empirical scenarios."""

from collections.abc import Sequence
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from gasopt.config import ExperimentConfig
from gasopt.data.dune import file_hash, utc_timestamp
from gasopt.types import Scenario, Transaction

PRICE_COLUMNS = ("median_gas_price_gwei", "mean_gas_price_gwei", "p25_gas_price_gwei",
                 "p75_gas_price_gwei", "p95_gas_price_gwei")


def read_extract(path: str | Path) -> pd.DataFrame:
    """Read only a saved CSV/Parquet file; this function has no network path."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Real Dune extract is missing: {path}. See docs/phase2.md.")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    raise ValueError("Expected a local .csv or .parquet extract.")


def require_columns(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    """Fail clearly on schema drift or the wrong extract type."""
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def parse_utc(values: pd.Series) -> pd.Series:
    """Reject naive/non-UTC source timestamps rather than guessing a timezone."""
    for value in values:
        stamp = pd.Timestamp(value)
        if pd.isna(stamp) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
            raise ValueError("Every source timestamp must explicitly be UTC.")
    return pd.to_datetime(values, utc=True, format="mixed")


def _days(values: pd.Series) -> pd.Series:
    result = pd.to_datetime(values, utc=True, format="mixed", errors="raise")
    if result.isna().any() or not result.eq(result.dt.normalize()).all():
        raise ValueError("day must contain UTC calendar dates at midnight.")
    return result


def validate_daily_slots(frame: pd.DataFrame, config: ExperimentConfig) -> tuple[pd.DataFrame, dict]:
    """Reject malformed data; explicitly report and drop incomplete daily paths.

    Missing-day tolerances are fixed in advance and checked separately in TRAIN
    and TEST. Counts describe transaction-level source rows versus extract rows.
    """
    required = ("day", "slot", "slot_start_utc", "transaction_count", "valid_transaction_count",
                "median_gas_used", "unit_check_count", "unit_check_median_relative_error",
                "unit_check_p95_relative_error", *PRICE_COLUMNS)
    require_columns(frame, required)
    if frame.empty:
        raise ValueError("The slot extract is empty.")
    data = frame.copy()
    data["day"] = _days(data.day)
    data["slot_start_utc"] = parse_utc(data.slot_start_utc)
    start, end = pd.Timestamp(config.train_start, tz="UTC"), pd.Timestamp(config.test_end, tz="UTC")
    if not data.day.between(start, end).all():
        raise ValueError("Slot observations fall outside the configured extraction dates.")
    for name in ("slot", "transaction_count", "valid_transaction_count", "unit_check_count"):
        values = pd.to_numeric(data[name], errors="raise")
        if not np.isfinite(values).all() or not (values == np.floor(values)).all():
            raise ValueError(f"{name} must contain finite integers.")
        data[name] = values.astype("int64")
    if not data.slot.between(1, 12).all():
        raise ValueError("Slots must be integers 1 through 12.")
    if data.duplicated(["day", "slot"]).any():
        raise ValueError("Duplicated day/slot pair; never silently aggregate exports.")
    expected_start = data.day + pd.to_timedelta(2 * (data.slot - 1), unit="h")
    if not data.slot_start_utc.eq(expected_start).all():
        raise ValueError("UTC slot timestamp does not match day and two-hour slot index.")
    if (data.transaction_count <= 0).any() or (data.valid_transaction_count < 0).any():
        raise ValueError("Invalid transaction counts.")
    if (data.valid_transaction_count > data.transaction_count).any():
        raise ValueError("Valid transaction count exceeds raw source count.")
    for name in (*PRICE_COLUMNS, "median_gas_used"):
        data[name] = pd.to_numeric(data[name], errors="raise")
        nonmissing = data[name].dropna()
        if not np.isfinite(nonmissing).all() or (nonmissing <= 0).any():
            raise ValueError(f"{name} must be positive and finite when present.")
    missing_values = data[list(PRICE_COLUMNS) + ["median_gas_used"]].isna().any(axis=1)
    no_valid_rows = data.valid_transaction_count.eq(0)
    bad_days = set(data.loc[missing_values | no_valid_rows, "day"])
    good = data.loc[~data.day.isin(bad_days)]
    if not ((good.p25_gas_price_gwei <= good.median_gas_price_gwei)
            & (good.median_gas_price_gwei <= good.p75_gas_price_gwei)
            & (good.p75_gas_price_gwei <= good.p95_gas_price_gwei)).all():
        raise ValueError("Gas-price quantiles are not ordered.")
    for name in ("unit_check_median_relative_error", "unit_check_p95_relative_error"):
        values = pd.to_numeric(good[name], errors="raise")
        if not np.isfinite(values).all() or (values < 0).any() or (values > 1e-6).any():
            raise ValueError("Gas-price unit audit failed; reconcile wei/gwei with execution fees.")
    if ((good.unit_check_count < .99 * good.valid_transaction_count)
            | (good.unit_check_count > good.valid_transaction_count)).any():
        raise ValueError("Insufficient transaction fee coverage for the gas-price unit audit.")
    sizes = data.groupby("day").size()
    partial_days = set(sizes[sizes != 12].index) | bad_days
    retained = data.loc[~data.day.isin(partial_days)].sort_values(["day", "slot"]).reset_index(drop=True)
    report = {
        "raw_aggregate_rows": len(data), "raw_transaction_observations": int(data.transaction_count.sum()),
        "valid_transaction_observations": int(data.valid_transaction_count.sum()),
        "excluded_transaction_observations": int((data.transaction_count - data.valid_transaction_count).sum()),
        "raw_date_min": data.day.min().date().isoformat(), "raw_date_max": data.day.max().date().isoformat(),
        "retained_aggregate_rows": len(retained), "retained_daily_scenarios": retained.day.nunique(),
        "timezone": "UTC", "duplicate_day_slots": 0, "interpolation": "none",
        "dropped_days_with_missing_values": sorted(d.date().isoformat() for d in bad_days),
    }
    for split, lo, hi in (("train", config.train_start, config.train_end),
                           ("test", config.test_start, config.test_end)):
        calendar = pd.date_range(lo, hi, freq="D", tz="UTC")
        missing = calendar.difference(pd.DatetimeIndex(retained.day.unique()))
        report[f"{split}_expected_days"] = len(calendar)
        report[f"{split}_retained_days"] = len(calendar) - len(missing)
        report[f"{split}_dropped_or_absent_days"] = [d.date().isoformat() for d in missing]
        if len(missing):
            warnings.warn(f"{split.upper()}: removed/absent {len(missing)} of {len(calendar)} days: "
                          + ", ".join(report[f"{split}_dropped_or_absent_days"]), stacklevel=2)
        if len(missing) / len(calendar) > config.max_missing_day_fraction:
            raise ValueError(f"{split.upper()} missing-day fraction exceeds the prespecified tolerance. "
                             f"Missing dates: {report[f'{split}_dropped_or_absent_days']}")
    if retained.empty:
        raise ValueError("No complete daily trajectories remain.")
    return retained, report


def split_daily_slots(data: pd.DataFrame, config: ExperimentConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological partition; this operation does not estimate parameters."""
    train = data.loc[data.day.between(pd.Timestamp(config.train_start, tz="UTC"),
                                     pd.Timestamp(config.train_end, tz="UTC"))].copy()
    test = data.loc[data.day.between(pd.Timestamp(config.test_start, tz="UTC"),
                                    pd.Timestamp(config.test_end, tz="UTC"))].copy()
    if train.empty or test.empty or train.day.max() >= test.day.min():
        raise ValueError("Both nonoverlapping chronological splits must contain observations.")
    return train, test


def daily_scenarios(data: pd.DataFrame) -> tuple[Scenario, ...]:
    """One twelve-slot median-price trajectory per day, with equal probabilities."""
    require_columns(data, ("day", "slot", "median_gas_price_gwei"))
    if data.empty or data.duplicated(["day", "slot"]).any():
        raise ValueError("Empty scenario set or duplicate day/slot.")
    wide = data.pivot(index="day", columns="slot", values="median_gas_price_gwei").sort_index()
    if list(wide.columns) != list(range(1, 13)) or wide.isna().any().any():
        raise ValueError("Every scenario must contain exactly 12 complete slots.")
    if not np.isfinite(wide.to_numpy()).all() or (wide <= 0).any().any():
        raise ValueError("Scenario prices must be finite and positive.")
    return tuple(Scenario(pd.Timestamp(day).date().isoformat(), tuple(row), 1 / len(wide))
                 for day, row in zip(wide.index, wide.to_numpy()))


def build_workload(raw: pd.DataFrame, config: ExperimentConfig) -> tuple[tuple[Transaction, ...], pd.DataFrame, dict]:
    """Select actual TRAIN observations at representative ranks, then assign business windows.

    Values are never interpolated/winsorized: nearest observed quantile ranks
    select entire source rows. Timing is deterministic and is NOT blockchain data.
    """
    require_columns(raw, ("day", "block_time_utc", "tx_hash", "gas_used"))
    data = raw.copy()
    data["day"] = _days(data.day)
    data["block_time_utc"] = parse_utc(data.block_time_utc)
    if data.empty or not data.day.between(pd.Timestamp(config.train_start, tz="UTC"),
                                         pd.Timestamp(config.train_end, tz="UTC")).all():
        raise ValueError("Workload observations must come exclusively from TRAIN.")
    if not data.block_time_utc.dt.normalize().eq(data.day).all():
        raise ValueError("Workload timestamp and day disagree.")
    calendar = pd.date_range(config.train_start, config.train_end, tz="UTC")
    missing_days = calendar.difference(pd.DatetimeIndex(data.day.unique()))
    if len(missing_days) / len(calendar) > config.max_missing_day_fraction:
        raise ValueError("Workload sample is missing too many TRAIN days; check for a truncated export.")
    if data.groupby("day").size().gt(config.sample_per_day).any():
        raise ValueError("Workload sample exceeds the configured per-day extraction limit.")
    data["tx_hash"] = data.tx_hash.astype(str).str.lower()
    if not data.tx_hash.str.fullmatch(r"0x[0-9a-f]{64}").all() or data.tx_hash.duplicated().any():
        raise ValueError("Workload requires unique real-format transaction hashes.")
    gas = pd.to_numeric(data.gas_used, errors="raise")
    if not np.isfinite(gas).all() or (gas <= 0).any() or not gas.eq(np.floor(gas)).all():
        raise ValueError("Observed gas use must be positive integers.")
    data["gas_used"] = gas.astype("int64")
    bounded = data.loc[data.gas_used.between(config.gas_used_min, config.gas_used_max)]
    if bounded.empty:
        raise ValueError("No gas observations survive the documented workload bounds.")
    low, high = bounded.gas_used.quantile([config.workload_trim_lower, config.workload_trim_upper], interpolation="nearest")
    trimmed = bounded.loc[bounded.gas_used.between(low, high)].sort_values(["gas_used", "block_time_utc", "tx_hash"])
    if len(trimmed) < config.transaction_count:
        raise ValueError("Insufficient distinct TRAIN observations for the requested fixed workload.")
    ranks = np.rint(np.linspace(0, len(trimmed) - 1, config.transaction_count)).astype(int)
    chosen = trimmed.iloc[ranks].copy().reset_index(drop=True)
    chosen = chosen.iloc[np.random.default_rng(config.sample_seed).permutation(len(chosen))].reset_index(drop=True)
    classes = (("URGENT", config.urgent_window), ("STANDARD", config.standard_window),
               ("FLEXIBLE", config.flexible_window))
    transactions, rows = [], []
    for index, row in enumerate(chosen.itertuples(index=False)):
        priority, width = classes[index % 3]
        release = 1 + (index // 3) % (13 - width)
        deadline = release + width - 1
        tx = Transaction(f"treasury_{index + 1:02d}", int(row.gas_used), deadline, release, priority)
        transactions.append(tx)
        rows.append({"transaction_id": tx.id, "gas_used": tx.gas_used, "release_slot": release,
                     "deadline_slot": deadline, "priority_class": priority,
                     "source_tx_hash": row.tx_hash, "source_block_time_utc": row.block_time_utc,
                     "gas_usage_origin": "observed training transaction",
                     "timing_origin": "explicit business assumption"})
    info = {"raw_sample_rows": len(data), "bounded_rows": len(bounded), "trimmed_rows": len(trimmed),
            "trim_lower_gas": int(low), "trim_upper_gas": int(high), "transaction_count": len(rows),
            "training_days_in_sample": int(data.day.nunique()), "seed": config.sample_seed,
            "missing_training_days": [day.date().isoformat() for day in missing_days],
            "method": "nearest observed ranks of trimmed TRAIN sample; seeded permutation before business windows",
            "gas_filter": [config.gas_used_min, config.gas_used_max], "winsorization": "none"}
    return tuple(transactions), pd.DataFrame(rows), info


def load_provenance(path: Path, config: ExperimentConfig, kind: str) -> dict:
    """Require empirical origin, consistent dates/units, exact query and file hash."""
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    if not sidecar.exists():
        raise FileNotFoundError(f"Missing provenance sidecar {sidecar}; archive the Dune extract first.")
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    if (meta.get("data_kind") != "empirical" or meta.get("source") != "Dune Analytics gas.fees"
            or meta.get("blockchain") != "ethereum" or meta.get("extract_kind") != kind):
        raise ValueError("The scientific pipeline requires a Dune Ethereum empirical extract.")
    if meta.get("sha256") != file_hash(path):
        raise ValueError("Extract hash mismatch; the archived input was modified.")
    if not meta.get("sql") or meta.get("sql_sha256") != sha256(meta["sql"].encode()).hexdigest():
        raise ValueError("Missing or inconsistent extraction SQL provenance.")
    utc_timestamp(meta["extracted_at_utc"])
    fields = ["train_start", "train_end", "dune_gas_price_unit"]
    fields += ["test_start", "test_end"] if kind == "slots" else ["sample_seed", "sample_per_day", "gas_used_min", "gas_used_max"]
    if any(meta.get("config", {}).get(field) != config.to_dict()[field] for field in fields):
        raise ValueError("Extraction settings differ from the experiment config; use a matching extract.")
    return meta


def prepare_local_data(slots_path: Path, workload_path: Path, config: ExperimentConfig, output: Path) -> dict:
    """Validate archived inputs and persist Parquet plus complete metadata offline."""
    # Read missing-file errors before sidecar errors, so setup instructions are clear.
    slots, workload = read_extract(slots_path), read_extract(workload_path)
    provenance = {"slots": load_provenance(slots_path, config, "slots"),
                  "workload": load_provenance(workload_path, config, "workload")}
    clean, quality = validate_daily_slots(slots, config)
    _, selected, construction = build_workload(workload, config)
    output.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(output / "ethereum_daily_slots.parquet", index=False)
    workload.to_parquet(output / "ethereum_workload_observations.parquet", index=False)
    selected.to_parquet(output / "treasury_workload.parquet", index=False)
    metadata = {"data_kind": "empirical", "source": "Dune Analytics gas.fees", "config": config.to_dict(),
                "provenance": provenance, "quality": quality, "workload_construction": construction,
                "processed_hashes": {name: file_hash(output / name) for name in (
                    "ethereum_daily_slots.parquet", "ethereum_workload_observations.parquet", "treasury_workload.parquet")}}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata
