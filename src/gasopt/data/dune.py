"""Dune extraction and manual import. Offline study code never calls this API."""

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from gasopt.config import ExperimentConfig, load_config


def file_hash(path: str | Path) -> str:
    """SHA-256 of a local file, used to audit input/output reproducibility."""
    return sha256(Path(path).read_bytes()).hexdigest()


def render_sql(template: str | Path, config: ExperimentConfig) -> str:
    """Substitute validated config values into the checked-in DuneSQL template."""
    values = config.to_dict() | {
        "start_date": config.train_start.isoformat(), "end_date": config.test_end.isoformat(),
        "end_exclusive": (config.test_end + timedelta(days=1)).isoformat(),
        "train_end_exclusive": (config.train_end + timedelta(days=1)).isoformat(),
        "raw_to_gwei": "1e-9" if config.dune_gas_price_unit == "wei" else "1.0",
    }
    sql = Path(template).read_text(encoding="utf-8")
    for name, value in values.items():
        sql = sql.replace("{{" + name + "}}", str(value))
    if "{{" in sql:
        raise ValueError("Unresolved SQL template parameter.")
    return sql


def utc_timestamp(value: str) -> str:
    """Require an explicit UTC timestamp for extraction provenance."""
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("Extraction timestamp must explicitly specify UTC (Z or +00:00).")
    return stamp.isoformat()


def write_provenance(
    path: Path, sql: str, config: ExperimentConfig, kind: str, extracted_at: str,
    source_reference: str, method: str,
) -> Path:
    """Save query, exact config, units, date range and immutable extract hash."""
    metadata = {
        "data_kind": "empirical", "source": "Dune Analytics gas.fees", "blockchain": "ethereum",
        "extract_kind": kind, "extraction_method": method, "source_reference": source_reference,
        "extracted_at_utc": utc_timestamp(extracted_at),
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_name": path.name, "sha256": file_hash(path), "sql": sql,
        "sql_sha256": sha256(sql.encode()).hexdigest(), "config": config.to_dict(),
        "units": {"gas_price_raw": config.dune_gas_price_unit, "gas_price_gwei": "gwei/gas",
                  "gas_used": "gas", "tx_fee_eth": "ETH", "tx_fee_usd": "USD (audit only)"},
        "aggregation": "Dune approx_percentile per UTC day and 2-hour slot" if kind == "slots"
                       else "TRAIN-only hash-prefix, seeded hash ordering, day-stratified sample",
        "timezone": "UTC",
    }
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return sidecar


def import_extract(
    source: Path, destination: Path, sql: str, config: ExperimentConfig, kind: str,
    extracted_at: str, source_reference: str,
) -> Path:
    """Archive a manual CSV/Parquet export without transforming observations."""
    utc_timestamp(extracted_at)
    if source.suffix.lower() not in (".csv", ".parquet") or destination.suffix.lower() != source.suffix.lower():
        raise ValueError("Use matching .csv or .parquet source and destination extensions.")
    if not source_reference.strip():
        raise ValueError("Provide the Dune query URL or execution ID for provenance.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return write_provenance(destination, sql, config, kind, extracted_at, source_reference, "manual export")


def dune_request(path: str, body: dict | None = None) -> dict:
    """One authenticated API request; never log or persist the API key."""
    key = os.environ.get("DUNE_API_KEY")
    if not key:
        raise RuntimeError("DUNE_API_KEY is not configured. Use the manual import path instead.")
    request = Request("https://api.dune.com/api/v1/" + path,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={"X-Dune-API-Key": key, "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as exc:
        # Report only the API's error message, never headers or a raw response body.
        try:
            error = json.loads(exc.read()).get("error", "")
            message = error.get("message", "") if isinstance(error, dict) else str(error)
            message = message.replace(key, "[REDACTED]")[:1000]
        except (ValueError, AttributeError):
            message = "Check access, credits and query syntax."
        raise RuntimeError(f"Dune returned HTTP {exc.code}: {message}") from None


def extract(
    sql: str, config: ExperimentConfig, kind: str, destination: Path,
    execution_id: str | None = None, timeout_seconds: int = 1800,
) -> Path:
    """Execute once, poll and download every result page; resumable by execution ID.

    API calls may consume Dune credits. No automatic POST retry or partial-result
    opt-in is used. A timed-out remote execution is left resumable, not resubmitted.
    """
    manifest = destination.with_suffix(".execution.json")
    sql_digest = sha256(sql.encode()).hexdigest()
    if execution_id is None:
        execution_id = dune_request("sql/execute", {"sql": sql, "performance": "medium"})["execution_id"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"execution_id": execution_id, "sql_sha256": sql_digest,
                                        "kind": kind}, indent=2), encoding="utf-8")
    else:
        if not manifest.exists():
            raise ValueError("Resume requires the original local .execution.json manifest.")
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        if saved != {"execution_id": execution_id, "sql_sha256": sql_digest, "kind": kind}:
            raise ValueError("Resume SQL/execution mismatch; provenance cannot be verified.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", execution_id):
        raise ValueError("Invalid execution ID.")
    print(f"Dune execution ID ({kind}): {execution_id}", flush=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        status = dune_request(f"execution/{execution_id}/status")
        state = status["state"]
        if state == "QUERY_STATE_COMPLETED":
            break
        if state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED", "QUERY_STATE_EXPIRED"):
            error = status.get("error", {})
            message = error.get("message", "") if isinstance(error, dict) else str(error)
            key = os.environ.get("DUNE_API_KEY", "")
            if key:
                message = message.replace(key, "[REDACTED]")
            raise RuntimeError(f"Dune execution {execution_id}: {state}. {message[:1000]}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"Dune is still running; resume with --execution-id {execution_id}")
        time.sleep(5)
    rows, offset, total = [], 0, None
    while True:
        page = dune_request(f"execution/{execution_id}/results?limit=5000&offset={offset}")
        result = page["result"]
        batch = result["rows"]
        total = result["metadata"]["total_row_count"]
        rows.extend(batch)
        if len(rows) >= total:
            break
        next_offset = page.get("next_offset", offset + len(batch))
        if not batch or next_offset <= offset:
            raise RuntimeError("Incomplete Dune pagination; no extract will be saved.")
        offset = next_offset
    if len(rows) != total or not rows:
        raise RuntimeError("Empty, duplicated or truncated result; no extract will be saved.")
    if destination.suffix.lower() != ".csv":
        raise ValueError("API extraction output must be .csv.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(destination, index=False)
    return write_provenance(destination, sql, config, kind,
                            status["execution_ended_at"], execution_id, "Dune API execution")


def main() -> None:
    """Render, extract or import the two small, separately auditable datasets."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("render", "extract", "import"):
        item = sub.add_parser(command)
        item.add_argument("--config", type=Path, default=Path("config/empirical.toml"))
        item.add_argument("--kind", choices=("slots", "workload"), required=True)
        item.add_argument("--output", type=Path, required=True)
        if command == "extract":
            item.add_argument("--execution-id")
        if command == "import":
            item.add_argument("--input", type=Path, required=True)
            item.add_argument("--query", type=Path, required=True, help="Exact SQL actually executed")
            item.add_argument("--extracted-at", required=True)
            item.add_argument("--source-reference", required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    template = Path("sql") / ("ethereum_gas.sql" if args.kind == "slots" else "ethereum_workload.sql")
    sql = render_sql(template, config)
    if args.command == "render":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(sql, encoding="utf-8")
    elif args.command == "extract":
        extract(sql, config, args.kind, args.output, args.execution_id)
    else:
        actual_sql = args.query.read_text(encoding="utf-8")
        if actual_sql.strip() != sql.strip():
            raise ValueError("Executed SQL differs from the configured template. Reconcile before importing.")
        import_extract(args.input, args.output, actual_sql, config, args.kind,
                       args.extracted_at, args.source_reference)
    print(args.output)


if __name__ == "__main__":
    main()
