# Phase 2 empirical status

**Phase 2 is complete and was executed on Ethereum Mainnet observations on
2026-09-24.** The code, archived extracts, processed Parquet files, notebooks,
tables, report and PNG/PDF figures have all been generated and validated locally.

## Data actually used

| Item | Observed result |
|:--|:--|
| Source | Dune Analytics `gas.fees`, `blockchain = 'ethereum'` |
| Slot execution | `01M39QBXRCQGR7AAMGG56JB2GC` |
| Workload execution | `01M39QFP26T5K5X07E6YW2926F` |
| TRAIN | 2025-01-01 through 2025-12-31, 365 complete UTC days |
| TEST | 2026-01-01 through 2026-03-31, 90 complete UTC days |
| Aggregates | 5,460 day-slot rows: 455 days x 12 two-hour slots |
| Underlying source rows | 724,380,678 transactions; all 724,380,678 passed the positivity checks |
| Missing/excluded data | 0 missing days, 0 incomplete days, 0 excluded transaction observations, no interpolation |
| Workload source sample | 23,360 TRAIN transactions: exactly 64 per day |
| Fixed workload | 30 actual observed integer `gas_used` values; 10 URGENT, 10 STANDARD, 10 FLEXIBLE |
| Tail mass at alpha=.95 | 18.25 TRAIN scenario equivalents; 4.50 TEST scenario equivalents |
| Dune usage after extraction | 31.401 of 2,500 included credits |

The live fee-identity check confirmed that Ethereum `gas_price` is raw wei in
the queried Dune view. The conversion to gwei is therefore `1e-9`. Across all
retained slots, the largest p95 relative fee-identity error was
`4.44e-16`, far below the fixed `1e-6` tolerance.

## Out-of-sample results

All schedules were fitted using TRAIN only, frozen, and evaluated on the 90 TEST
days. Savings compare mean TEST cost with immediate execution.

| Strategy | Mean cost (ETH) | CVaR95 (ETH) | Worst day (ETH) | Savings vs immediate |
|:--|--:|--:|--:|--:|
| Immediate | 0.000418475 | 0.002673774 | 0.007177719 | 0.000% |
| Mean price / lambda=0 | 0.000299349 | 0.001928617 | 0.003541723 | 28.467% |
| CVaR lambda=.05 | 0.000303181 | 0.001801969 | 0.003466074 | 27.551% |
| CVaR lambda=.10-2.00 | 0.000306412 | 0.001853447 | 0.003658447 | 26.779% |
| CVaR lambda=3-5 | 0.000308789 | 0.001846015 | 0.003659716 | 26.211% |

The mean-price and explicit expected-value objectives agree exactly. The
prespecified risk grid produced four distinct CVaR schedules. Relative to the
mean-price schedule, lambda=.05 increased TEST mean cost by 1.28% while reducing
TEST CVaR95 by 6.57% and the worst observed daily cost by 2.14%. This is an
out-of-sample descriptive comparison, not a TEST-based lambda selection.

Schedules below list the assigned one-based slot for `treasury_01` through
`treasury_30`:

- Mean price / lambda=0: `(1,3,3,3,3,3,3,3,3,4,4,4,5,5,5,6,6,3,7,7,3,9,11,3,10,12,4,11,3,5)`
- CVaR lambda=.05: `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,12,4,11,4,5)`
- CVaR lambda=.10-2.00: `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)`
- CVaR lambda=3-5: `(1,4,4,3,4,5,4,5,4,5,5,5,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)`

## Validation and deliverables

`python -m pytest -q --basetemp=tmp/pytest-phase2` reports **94 passed**. Both
empirical notebooks were executed from top to bottom against the archived data.
Every optimization terminated optimally; the risk-neutral model has 140 binary
variables and 30 constraints, while each positive-lambda model has 506 variables,
including 140 binaries, and 395 constraints before presolve.

The primary readable result is `outputs/empirical/report.md`. Machine-readable
TRAIN/TEST metrics, all assignments, daily TEST costs, study metadata and the
fixed workload are in the same directory. Ten empirical figures are available
as both PNG and PDF. The exact SQL and file hashes are preserved in the raw and
processed metadata sidecars, so all preparation and optimization steps rerun
offline without the API key.

The 95% TEST tail contains only 4.5 day equivalents, so its CVaR estimate is
imprecise. Slot medians are execution-price proxies rather than attainable-price
guarantees, and timing windows remain explicit business assumptions. No
statistical significance or production execution guarantee is claimed.
