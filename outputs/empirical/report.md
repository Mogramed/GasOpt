# GasOpt empirical study

Source: Dune Analytics `gas.fees`, Ethereum Mainnet.
TRAIN: 2025-01-01 to 2025-12-31 (inclusive UTC).
TEST: 2026-01-01 to 2026-03-31 (inclusive UTC).

Retained scenarios: 365 TRAIN; 90 TEST.
Tail scenario equivalents: 18.25 TRAIN; 4.50 TEST.

## Data and provenance

- Dune slot execution: `01M39QBXRCQGR7AAMGG56JB2GC`
- Dune workload execution: `01M39QFP26T5K5X07E6YW2926F`
- Aggregated day-slot rows: 5,460
- Underlying source transactions: 724,380,678
- Excluded source transactions: 0
- Missing or incomplete retained days: 0
- TRAIN workload observations: 23,360; selected actual observations: 30
- Interpolation: none; winsorization: none

## Training diagnostics

| Strategy | Lambda | Expected ETH | CVaR ETH | Worst ETH | Objective ETH | Status |
|:--|--:|--:|--:|--:|--:|:--|
| immediate | 0 | 0.005185655 | 0.037625712 | 0.131146366 | 0.005185655 | not_applicable_baseline |
| mean_price | 0 | 0.004407514 | 0.034154280 | 0.119536639 | 0.004407514 | optimal |
| expected_value_equivalence | 0 | 0.004407514 | 0.034154280 | 0.119536639 | 0.004407514 | optimal |
| cvar_lambda_0 | 0 | 0.004407514 | 0.034154280 | 0.119536639 | 0.004407514 | optimal |
| cvar_lambda_0.05 | 0.05 | 0.004488570 | 0.031412102 | 0.099466097 | 0.006059175 | optimal |
| cvar_lambda_0.1 | 0.1 | 0.004492165 | 0.031358941 | 0.099605485 | 0.007628059 | optimal |
| cvar_lambda_0.25 | 0.25 | 0.004492165 | 0.031358941 | 0.099605485 | 0.012331900 | optimal |
| cvar_lambda_0.5 | 0.5 | 0.004492165 | 0.031358941 | 0.099605485 | 0.020171635 | optimal |
| cvar_lambda_0.75 | 0.75 | 0.004492165 | 0.031358941 | 0.099605485 | 0.028011370 | optimal |
| cvar_lambda_1 | 1 | 0.004492165 | 0.031358941 | 0.099605485 | 0.035851105 | optimal |
| cvar_lambda_1.5 | 1.5 | 0.004492165 | 0.031358941 | 0.099605485 | 0.051530576 | optimal |
| cvar_lambda_2 | 2 | 0.004492165 | 0.031358941 | 0.099605485 | 0.067210046 | optimal |
| cvar_lambda_3 | 3 | 0.004531036 | 0.031344934 | 0.097731603 | 0.098565838 | optimal |
| cvar_lambda_5 | 5 | 0.004531036 | 0.031344934 | 0.097731603 | 0.161255706 | optimal |

## Frozen schedules

Slots are one-based and ordered from `treasury_01` through `treasury_30`.

| Strategy | Assigned slots |
|:--|:--|
| immediate | `(1,1,1,2,2,2,3,3,3,4,4,4,5,5,5,6,6,1,7,7,2,8,8,3,9,9,4,10,1,5)` |
| mean_price | `(1,3,3,3,3,3,3,3,3,4,4,4,5,5,5,6,6,3,7,7,3,9,11,3,10,12,4,11,3,5)` |
| expected_value_equivalence | `(1,3,3,3,3,3,3,3,3,4,4,4,5,5,5,6,6,3,7,7,3,9,11,3,10,12,4,11,3,5)` |
| cvar_lambda_0 | `(1,3,3,3,3,3,3,3,3,4,4,4,5,5,5,6,6,3,7,7,3,9,11,3,10,12,4,11,3,5)` |
| cvar_lambda_0.05 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,12,4,11,4,5)` |
| cvar_lambda_0.1 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_0.25 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_0.5 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_0.75 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_1 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_1.5 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_2 | `(1,4,4,3,4,4,4,4,4,4,4,4,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_3 | `(1,4,4,3,4,5,4,5,4,5,5,5,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |
| cvar_lambda_5 | `(1,4,4,3,4,5,4,5,4,5,5,5,5,5,5,6,6,4,7,7,4,9,11,4,10,11,4,11,4,5)` |

## Out-of-sample comparison

| Strategy | Mean ETH | CVaR ETH | Worst ETH | Savings ETH | Savings % |
|:--|--:|--:|--:|--:|--:|
| immediate | 0.000418475 | 0.002673774 | 0.007177719 | 0.000000000 | 0.000 |
| mean_price | 0.000299349 | 0.001928617 | 0.003541723 | 0.000119126 | 28.467 |
| cvar_lambda_0 | 0.000299349 | 0.001928617 | 0.003541723 | 0.000119126 | 28.467 |
| cvar_lambda_0.05 | 0.000303181 | 0.001801969 | 0.003466074 | 0.000115295 | 27.551 |
| cvar_lambda_0.1 | 0.000306412 | 0.001853447 | 0.003658447 | 0.000112064 | 26.779 |
| cvar_lambda_0.25 | 0.000306412 | 0.001853447 | 0.003658447 | 0.000112064 | 26.779 |
| cvar_lambda_0.5 | 0.000306412 | 0.001853447 | 0.003658447 | 0.000112064 | 26.779 |
| cvar_lambda_0.75 | 0.000306412 | 0.001853447 | 0.003658447 | 0.000112064 | 26.779 |
| cvar_lambda_1 | 0.000306412 | 0.001853447 | 0.003658447 | 0.000112064 | 26.779 |
| cvar_lambda_1.5 | 0.000306412 | 0.001853447 | 0.003658447 | 0.000112064 | 26.779 |
| cvar_lambda_2 | 0.000306412 | 0.001853447 | 0.003658447 | 0.000112064 | 26.779 |
| cvar_lambda_3 | 0.000308789 | 0.001846015 | 0.003659716 | 0.000109686 | 26.211 |
| cvar_lambda_5 | 0.000308789 | 0.001846015 | 0.003659716 | 0.000109686 | 26.211 |

Distinct CVaR schedules across the prespecified grid: 4.
Mean-price and expected-value objectives agree; C is a pedagogical equivalence check.
No risk weight is selected using TEST performance. See train_metrics.csv for objectives, VaR/CVaR, solver status, bounds and model dimensions; schedules.csv contains every assignment.

## Limits

Slot medians are execution-price proxies, not attainable-price guarantees. Timing classes are business assumptions. Serial dependence, regime changes, gas-use uncertainty, nonce constraints and inclusion uncertainty remain outside the model. The small TEST tail limits precision; no statistical significance is claimed.
