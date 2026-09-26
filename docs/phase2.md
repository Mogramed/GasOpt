# Phase 2: real Ethereum data and offline empirical optimization

The implementation extends Phase 1; it does not replace its synthetic validation.
The empirical run was completed on 2026-09-24 using archived Dune Ethereum
observations. Test fixtures remain explicitly labelled and are never presented
as measured Ethereum results.

## Fixed experimental design

Settings live in `config/empirical.toml`. Dates are inclusive UTC calendar dates:

| Split | Start | End | Retained days | 5% tail mass |
|:--|:--|:--|--:|--:|
| TRAIN | 2025-01-01 | 2025-12-31 | 365 | 18.25 scenario equivalents |
| TEST | 2026-01-01 | 2026-03-31 | 90 | 4.50 scenario equivalents |

Source coverage was verified: all 455 configured days contain all 12 slots. Each
complete day is one scenario,
with 12 two-hour slots: slot 1 is [00:00,02:00), slot 12 is [22:00,24:00).
Missing days/slots are reported and removed, without interpolation. The fixed
maximum removal fraction is 5% **separately in each split**. Excessive loss stops
the study instead of silently changing dates. Missing price values also remove
the entire day. Duplicates, nonpositive observations, timezone errors, misaligned
slots and failed unit audits stop preparation.

TRAIN alone determines the fixed workload, mean prices, scenario probabilities
and every optimized schedule. TEST cannot influence lambda selection. The
prespecified grid is `[0, .05, .10, .25, .50, .75, 1, 1.5, 2, 3, 5]`; alternative
grids should be explored using TRAIN or an inner chronological validation split.
Do not choose a winning lambda from the reported TEST results.

The default minimum TRAIN tail mass is 10 scenario equivalents. A smaller tail
issues a warning and stops fitting; acquire more scenarios or choose a lower
alpha before evaluating TEST. TEST tail mass is always reported, with a warning
below 10. Tail mass can be fractional and is not a count rounded down to days.
Serial dependence means 18.25 equivalents need not be 18.25 independent observations.

## Source, SQL and a critical unit discrepancy

Primary source: Dune Analytics `gas.fees`, filtered to `blockchain = 'ethereum'`.
The SQL uses explicit `block_month`, `block_date` and `block_time` bounds.

- `sql/ethereum_gas.sql`: two-hour aggregates over TRAIN and TEST. Output includes
  raw/valid transaction counts, mean and approximate p25/median/p75/p95 gas price,
  median gas usage, raw median gas price, mean native/USD fee and fee-unit checks.
- `sql/ethereum_workload.sql`: training-only transaction-level sample, retaining
  original transaction hash, timestamp, integer gas usage, raw/normalized price
  and native/USD fee fields. No test gas usage enters this query.
- `sql/rendered/`: the exact runnable queries for the default configuration.
  Re-render after changing extraction settings. Rendering never contacts Dune.

The [Dune schema documentation](https://docs.dune.com/data-catalog/curated/gas-fees/fees)
labels `gas_price` as gwei. However, the official
[Ethereum Spellbook model](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/models/_sector/gas/fees/ethereum/gas_ethereum_fees.sql)
passes the raw transaction gas price through, multiplies it by gas usage to form
raw fees, and converts fees by the native-token decimals. The
[aggregate view](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/models/_sector/gas/fees/gas_fees.sql)
passes that same field through. These disagree about units.

The configuration therefore explicitly defaults `dune_gas_price_unit = "wei"`,
consistent with the Ethereum implementation. The SQL converts it to gwei with
`raw_to_gwei = 1e-9`; choosing `gwei` sets this factor to 1. This is **not** an
automatic magnitude heuristic. The import must pass an independent per-transaction
fee identity audit before any normalized prices enter the model:

$$\epsilon=\left|\frac{\text{gas\_price\_gwei}\times\text{gas\_used}\times10^{-9}}
{\text{tx\_fee}-\text{blob\_fee}}-1\right|.$$

Both median and p95 relative error must be at most $10^{-6}$ per retained slot,
with audit coverage of at least 99% of valid transactions. A wrong factor of
$10^9$ fails this check. Inspect the discrepancy if extraction fails; never
change scaling merely to obtain attractive costs. USD fields are kept only for
provenance and are not used in costs or optimization.

Under EIP-1559 the execution price includes base fee and priority fee; base fee
alone is not the full execution price. Blob charges are a distinct resource and
are removed only for the fee identity audit. The treasury cost proxy concerns
execution gas, excludes blob charges, and is not a promise of actual inclusion at
a slot median. We do not simulate bidding, mempool behavior or smart contracts.

Slot quantiles use DuneSQL `approx_percentile` for efficient aggregation, not
exact order statistics. The persisted extract is the reproducible input; source
backfills or query-engine changes can change a future re-extraction. Each archive
stores exact SQL, its SHA-256, extraction timestamp, query/execution reference,
source units, dates and the extract's SHA-256. Raw local rows are aggregates,
not all source transactions; `sum(transaction_count)` is the underlying source
row count. No full Mainnet transaction download is required.

## Extraction and installation

Run from the repository root in PowerShell. The existing virtual environment can
be reused. After the final dependency snapshot is present:

```powershell
.\.venv\Scripts\python.exe -m pip install -c requirements-lock.txt -e '.[dev]'
.\.venv\Scripts\python.exe -m gasopt.data.dune render --kind slots --output sql/rendered/ethereum_gas.sql
.\.venv\Scripts\python.exe -m gasopt.data.dune render --kind workload --output sql/rendered/ethereum_workload.sql
```

**Manual route:** run the rendered queries in Dune and export the full results
as CSV or Parquet. A preview page or truncated table is not a complete export.
Archive each export with its actual UTC extraction timestamp and query URL:

```powershell
.\.venv\Scripts\python.exe -m gasopt.data.dune import --kind slots --input 'C:/path/to/slots.csv' --output data/raw/ethereum_slots.csv --query sql/rendered/ethereum_gas.sql --extracted-at '2026-09-23T12:00:00Z' --source-reference 'https://dune.com/queries/YOUR_SLOT_QUERY_ID'
.\.venv\Scripts\python.exe -m gasopt.data.dune import --kind workload --input 'C:/path/to/workload.csv' --output data/raw/ethereum_workload.csv --query sql/rendered/ethereum_workload.sql --extracted-at '2026-09-23T12:05:00Z' --source-reference 'https://dune.com/queries/YOUR_WORKLOAD_QUERY_ID'
```

The paths, timestamps and query IDs above are **placeholders to replace with the
actual export details**. For Parquet keep `.parquet` at both source and destination,
and pass those paths to preparation. Imports require the actual executed SQL to
match the rendered configuration. Query changes should be reviewed and reflected
in the checked-in template rather than hidden in a metadata label.

**API route:** configure `DUNE_API_KEY` locally. Never commit or paste keys into
source or notebooks. No key is needed after extraction. API requests may consume
Dune credits; this program neither purchases credits nor bypasses account limits.

```powershell
.\.venv\Scripts\python.exe -m gasopt.data.dune extract --kind slots --output data/raw/ethereum_slots.csv
.\.venv\Scripts\python.exe -m gasopt.data.dune extract --kind workload --output data/raw/ethereum_workload.csv
```

The adapter uses the documented [Execute SQL endpoint](https://docs.dune.com/api-reference/executions/endpoint/execute-sql)
and paginated execution results. It logs an execution ID, not a secret. It does
not retry execution POSTs, accept partial results, or use “latest result” for
provenance. After a timeout, resume with the printed `--execution-id` and the
same output path/config; the local execution manifest must match the SQL hash.
The API adapter was verified by the two archived executions recorded in the raw
metadata sidecars.

## Offline preparation and run

Once both archived extracts and their `.metadata.json` sidecars exist, all
remaining commands require **no network**:

```powershell
.\.venv\Scripts\python.exe -m gasopt.empirical_study prepare
.\.venv\Scripts\python.exe -m gasopt.empirical_study run
.\.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest-phase2
```

Both study commands accept `--config`, `--processed` and `--output`; preparation
also accepts `--slots` and `--workload`. Defaults point to the paths above.
The explicit local pytest temporary directory avoids a Windows permission issue
seen during cleanup of the shared system temporary directory.

Preparation writes `data/processed/ethereum_daily_slots.parquet`,
`ethereum_workload_observations.parquet`, `treasury_workload.parquet` and
`metadata.json`. Hash verification detects later changes to archived or processed
data. Reprepare from matching archived extracts when changing dates or workload
rules; alpha and lambda can change without downloading the data again.

## Fixed empirical workload and business timing

The source query first filters training gas usage to [21,000, 1,000,000] gas.
These are explicit study bounds, not a claim that all Mainnet activity lies in
this range. It selects transaction hashes with prefix `000` (approximately
1/4096 of hashes), orders those candidates per day by a seeded hash and retains
up to 64 per day. This is a deterministic, day-stratified sample; it is not
transaction-frequency weighted across days and does not establish that the
selected activity is representative of a particular treasury.

Locally, remove values below the nearest observed 1st percentile or above the
nearest observed 99th percentile of this TRAIN sample. Choose 30 evenly spaced
ranks from the remaining ordered source rows. Each selected gas requirement is
an **actual observed integer value** with source hash/time; no interpolated gas
value, synthetic substitute or winsorized replacement is introduced. A fixed
seed permutes these representatives before applying timing classes.

Ten transactions each receive URGENT (2-slot), STANDARD (4-slot) and FLEXIBLE
(8-slot) windows. Releases are spread deterministically across admissible starting
slots. These windows are **business assumptions**, not blockchain measurements.
Every day reuses the same hypothetical workload and timing. This is a controlled
cost comparison, not a reconstruction of an actual treasury's historical orders.

## Mathematics and frozen-schedule evaluation

With one-based inclusive release/deadline indices, let
$A=\{(i,t):r_i\leq t\leq d_i\}$ and impose

$$x_{it}\in\{0,1\},\quad \sum_{t=r_i}^{d_i}x_{it}=1,\quad x_{it}=0\quad((i,t)\notin A).$$

Phase 1 remains compatible because omitted release slots default to 1.
All decisions are here-and-now, independent of scenario. For TRAIN days,

$$C_s(x)=10^{-9}\sum_{(i,t)\in A}g_i p_{ts}x_{it},\qquad q_s=1/S.$$

The deterministic objective uses the **mean across TRAIN days of the slot
medians**. This differs from the transaction-level mean field in the extract.
The equality $E[C(x)]=10^{-9}\sum g_i(\sum_s q_s p_{ts})x_{it}$ holds for every
feasible schedule even with release times. The explicit expected-value model is
retained in training diagnostics, not presented as a separate economic competitor
on TEST. Tied optima can have different schedules without invalidating equivalence.
The zero-lambda grid entry reuses the deterministic representative, so tie-breaking
cannot create an artificial difference in its reported TEST performance.

The CVaR objective and auxiliary constraints are unchanged from Phase 1:

$$\min E[C]+\lambda\left(\eta+\frac{1}{1-\alpha}\sum_s q_s\xi_s\right),
\qquad \xi_s\ge C_s-\eta,\quad\xi_s\ge0,\quad\eta\in\mathbb R.$$

With the 30 selected transactions there are 140 admissible binaries. All 365
TRAIN days survived, so every positive-lambda model has 506 variables and 395
explicit constraints before presolve. Every empirical solve terminated optimally;
the output reports status, bound and relative gap. Node count remains unavailable
through APPSI.

After fitting, the same schedule is evaluated on every TEST day. Immediate
execution assigns $x_{i,r_i}=1$. No test-day re-optimization occurs. TRAIN and
TEST metrics use separate names/files. For TEST, report mean, median, population
standard deviation (`ddof=0`), inverse-ECDF p95, VaR at configured alpha, exact
discrete CVaR, minimum and maximum. With alpha=.95, p95 and VaR use the same
quantile convention and agree. CVaR includes fractional probability atoms.

Principal savings are

$$\text{savings}_{ETH}=\overline C_{immediate}-\overline C_{strategy},\qquad
\text{savings}_{\%}=100\frac{\overline C_{immediate}-\overline C_{strategy}}{\overline C_{immediate}}.$$

This is a ratio of mean costs, not an average of daily percentages. Negative
savings are retained. In-sample objectives are never called out-of-sample savings.

## Notebooks and presentation outputs

```powershell
.\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name gasopt --display-name 'Python (GasOpt)'
.\.venv\Scripts\jupyter.exe nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=gasopt --ExecutePreprocessor.timeout=600 notebooks/02_real_data.ipynb
.\.venv\Scripts\jupyter.exe nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=gasopt --ExecutePreprocessor.timeout=600 notebooks/03_empirical_optimization.ipynb
```

The notebooks load the fixed configuration and local processed data. The second
shows provenance, data quality, distributions, slot profiles, a daily heatmap,
gas-use sampling and chronological scenarios. The third develops the mathematics
before fitting, then evaluates frozen schedules and interprets risk/cost results.

`outputs/empirical/` contains train/test CSV tables, daily TEST costs in CSV and
Parquet, every schedule, workload/source records, metadata, `report.md`, and ten
PNG/PDF figures. These include all eight requested presentation views plus TRAIN
price and gas-use distributions. Figure labels separate TRAIN and TEST; the
displayed schedule comparison uses the **prespecified maximum lambda**, not a
lambda chosen by TEST performance. No PowerPoint is created.

Archive raw extracts, sidecars, processed files and study outputs together for
submission. Raw extracts and generated figures are gitignored. The small,
verified runtime snapshot used by the Vercel application is versioned; code,
templates, rendered default SQL and notebooks remain versionable.

## Remaining empirical limitations

Complete-day removal may introduce selection bias, especially if outages are
related to congestion. Median prices suppress extremes within a slot, while
CVaR controls variation in daily costs built from those median proxies. Thus
this is not CVaR of every individual transaction's actual inclusion fee.

Chronological holdout reduces look-ahead bias but does not eliminate regime
change or temporal dependence. The 90-day TEST tail has only 4.5 scenario
equivalents at 95%; tail rankings may be unstable. We make no significance claim.
No forecast, adaptive policy, nonce/dependency handling, dynamic programming,
custom branch-and-bound, batching, Layer 2, MEV or USD optimization is included.
BigQuery can be a later independent validation source; no second pipeline exists.
React, FastAPI and Docker remain outside this phase.
