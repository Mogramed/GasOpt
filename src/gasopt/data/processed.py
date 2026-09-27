"""Read and verify the frozen processed dataset without importing solvers."""

import json
from pathlib import Path

import pandas as pd

from gasopt.config import ExperimentConfig
from gasopt.data.dune import file_hash
from gasopt.data.empirical import read_extract


def load_processed(directory: Path, config: ExperimentConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    meta_path = directory / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError("No verified empirical dataset. Run the prepare command after Dune extraction.")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if metadata.get("data_kind") != "empirical":
        raise ValueError("Scientific run requires empirical provenance, not a test fixture.")
    for name, digest in metadata["processed_hashes"].items():
        if file_hash(directory / name) != digest:
            raise ValueError(f"Processed data hash mismatch: {name}")
    settings = config.to_dict()
    reusable = {"alpha", "lambda_grid", "min_train_tail_count"}
    if any(metadata["config"].get(key) != value for key, value in settings.items() if key not in reusable):
        raise ValueError("Prepared data/config mismatch. Re-run prepare from matching archived extracts.")
    return (
        read_extract(directory / "ethereum_daily_slots.parquet"),
        read_extract(directory / "ethereum_workload_observations.parquet"),
        metadata,
    )
