# GasOpt

**Stochastic Optimization of Ethereum Transaction Fees under Gas-Price Uncertainty**

Research question: how should a crypto treasury schedule delay-tolerant Ethereum
transactions to minimize expected transaction costs while controlling exposure
to extreme gas-fee scenarios?

Phase 2 extends the validated engine with release times, Dune extraction/import,
whole-day empirical scenarios and offline chronological evaluation. The empirical
run uses 365 TRAIN days and 90 subsequent TEST days from Dune `gas.fees`; see the
[Phase 2 protocol and exact commands](docs/phase2.md) and the
[executed-study status](docs/phase2_status.md). Phase 1 tests remain explicitly
synthetic; Phase 3 also validates the API against the local empirical archive.

The Phase 1 validation remains available below, unchanged in its numerical setup.

## Phase 3 — GasOps interactive platform

GasOps wraps the existing `gasopt` scientific package with FastAPI and a React
research workspace: live TRAIN optimization, schedule comparison, data and
scenario explorers, progressive mathematics, CVaR and frozen TEST evaluation.
The scientific models and Phase 2 numerical artifacts remain unchanged.

```powershell
docker compose up --build
```

Open **http://localhost:3000**. Both containers have healthchecks; empirical data
and outputs are mounted read-only. No Dune API key or runtime Internet is needed.
The first build requires network access to install dependencies.

See [platform architecture, API, local launch and tests](docs/platform.md).
The [Phase 3 completion report](docs/phase3_status.md) records the delivered
features, validation results and unchanged scientific references.

Phase 3.1 adds a mathematical deep dive inside the existing `/model` and
`/solver` routes: complete scalar and matrix formulations, CVaR linearization,
gradient/Hessian context, LP bounds, and a fully calculated Branch-and-Bound
certificate. See the [Phase 3.1 completion report](docs/phase31_status.md).
The final [UI polish report](docs/ui_polish_status.md) covers equation rendering,
responsive layouts and browser checks on the production Docker build.
Keep `data/processed/` and `outputs/empirical/` when copying the demo to another
machine; these local archives are gitignored.

## Phase 1 — mathematical validation

This MSc Finance & Big Data project starts with mathematical validation.
**Every input in Phase 1 is synthetic. No empirical Ethereum data is used.**
The fixed example has five transactions, four slots and five equiprobable price
trajectories. All transactions are available at slot 1; deadlines are inclusive.

## Model

Let $i$ index transactions, $t$ slots and $s$ complete price scenarios. Gas usage
$g_i$ is in gas, $p_{ts}$ in gwei/gas, $d_i$ is the deadline and $q_s$ the scenario
probability. One common schedule is chosen before uncertainty is observed:

$$x_{it}\in\{0,1\},\qquad \sum_{t\leq d_i}x_{it}=1,\qquad x_{it}=0\quad(t>d_i).$$

For Phase 2, admissible pairs satisfy $r_i\le t\le d_i$ and the assignment sum
runs from $r_i$ through $d_i$. Omitted release times default to 1, preserving
the Phase 1 example. Forbidden pairs are omitted from the model and reported as zeros. Optional
transaction-count capacity is $\sum_i x_{it}\leq K_t$; it is disabled by default.

$$C_s(x)=10^{-9}\sum_{i,t}g_i p_{ts}x_{it},\qquad E[C]=\sum_s q_s C_s(x).$$

All cost expressions, auxiliary cost variables and returned cost metrics are in
**ETH**, including the deterministic objective. The risk-adjusted MILP is

$$\min_{x,\eta,\xi}\ E[C]+\lambda\left(\eta+\frac{1}{1-\alpha}\sum_s q_s\xi_s\right),$$
$$\eta\in\mathbb R,\quad \xi_s\geq0,\quad \xi_s\geq C_s(x)-\eta.$$

The deterministic mean-price and stochastic expected-cost objectives are
identical for every feasible schedule, including with optional capacities:

$$\sum_s q_s C_s(x)=10^{-9}\sum_{i,t}g_i\underbrace{\left(\sum_s q_s p_{ts}\right)}_{\bar p_t}x_{it}.$$

There is no recourse or scenario-dependent decision. Thus at $\lambda=0$ the
models have the same optimal value and optimal schedule set; tied optima may
produce different solver selections. The CVaR term can change the schedule.

At zero risk aversion, unused CVaR auxiliaries are omitted and risk is evaluated
independently after solving. `eta_eth` is the lower weighted empirical
$\alpha$-quantile; `solver_eta_eth` is the solver's possibly nonunique threshold
when $\lambda>0$. `solver_cvar_eth` allows comparison with independently
computed `cvar_eth`. `gas_cost_eth` aliases expected expenditure; the objective
also includes the risk penalty and is not a realized transaction bill.

## Structure

```text
src/gasopt/
  types.py                   # validated dataclasses, ETH-valued results
  data/synthetic.py          # the exact fixed synthetic inputs
  models/_common.py         # assignment constraints and audited HiGHS solve
  models/deterministic.py    # mean-price objective
  models/stochastic_cvar.py  # explicit scenario costs and CVaR epigraph
  evaluation/metrics.py     # independent weighted VaR/CVaR and cost evaluation
  experiment.py             # reproducible five-weight sensitivity table
notebooks/01_model_validation.ipynb
tests/                      # mathematical, exhaustive and input checks
data/raw/, data/processed/   # empty placeholders for later phases
requirements-lock.txt       # tested dependency versions (Python 3.12 / Windows)
```

## Install and run

From the repository root in **Windows PowerShell** (activation is unnecessary):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements-lock.txt -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest-phase2
.\.venv\Scripts\python.exe -m gasopt.experiment
.\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name gasopt --display-name 'Python (GasOpt)'
.\.venv\Scripts\jupyter.exe nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=gasopt --ExecutePreprocessor.timeout=120 notebooks/01_model_validation.ipynb
.\.venv\Scripts\jupyter.exe lab notebooks/01_model_validation.ipynb
```

Python 3.12+ is required. On macOS/Linux use `python3.12 -m venv .venv`, then
`.venv/bin/python` and `.venv/bin/jupyter` in place of the Windows executables.
The constraints file records the tested environment; it does not force
Windows-only dependencies to install on other platforms. Core runtime
dependencies are Pyomo, highspy, NumPy and pandas. Jupyter and pytest are in
the development extra. `highspy` supplies HiGHS; no external solver executable
is needed. No fallback solver was necessary in the validated environment.

The notebook is saved with executed outputs and shows input tables, objective
coefficients, binary assignments, per-transaction scenario costs, weighted
expectations, the equivalence proof, CVaR excesses, solver diagnostics and an
independent enumeration of all 96 feasible schedules. HiGHS handles the MILP;
enumeration is only a tiny-instance validation, not the optimization engine.

## Synthetic results

The weighted slot prices are **[12.8, 11.4, 8.8, 10.6] gwei/gas**. Schedules below
list slots for transactions 1–5. Every solve terminates optimally.

| $\lambda$ | Schedule | Expected cost (ETH) | CVaR$_{0.80}$ (ETH) | Worst cost (ETH) | Objective (ETH) |
|---:|:---|---:|---:|---:|---:|
| 0 | (1, 2, 3, 3, 3) | 0.0040722 | 0.005418 | 0.005418 | 0.0040722 |
| 0.1 | (1, 2, 3, 3, 3) | 0.0040722 | 0.005418 | 0.005418 | 0.0046140 |
| 0.25 | (1, 2, 3, 3, 3) | 0.0040722 | 0.005418 | 0.005418 | 0.0054267 |
| 0.5 | (1, 2, 3, 3, 3) | 0.0040722 | 0.005418 | 0.005418 | 0.0067812 |
| 1 | (1, 2, 3, 3, 4) | 0.0043962 | 0.005058 | 0.005058 | 0.0094542 |

At $\lambda=1$, moving transaction 5 to slot 4 increases expected expenditure
by 0.000324 ETH and reduces the worst cost by 0.000360 ETH. These two schedules
tie at $\lambda=0.9$, along with (1, 2, 4, 3, 3). Piecewise-constant decisions
are normal for a discrete model; unchanged schedules do not mean risk was ignored.

With five equal probabilities and $\alpha=0.80$, the upper tail has the mass of
exactly one scenario, so **CVaR equals worst-case cost**. A 95% CVaR can be
calculated but also collapses to the maximum here and gives no richer tail
information. The future empirical experiment may use $\alpha=0.95$ with many
more scenarios and adequate effective tail observations.

Tests check feasibility, binary values, manual ETH costs, fractional probability
atoms, solver CVaR consistency, zero-risk equivalence, weighted probabilities,
capacity limits, infeasibility and exhaustive optimality. Solver output exposes
model variable/constraint counts, objective bound and relative gap. Node count
is `None` because the public APPSI result does not expose it. Counts precede presolve.

## Limitations and roadmap

This is an in-sample mathematical demonstration, not evidence of real Ethereum
savings. Gas requirements and price trajectories are synthetic; deadlines and
capacity are explicit business assumptions. Slots have no physical duration yet.
Prices represent a simplified all-in execution price per gas, with no separate
base-fee/tip process, pending-pool behavior, bidding or inclusion guarantee.
Transactions are assumed independent, have fixed gas requirements and complete
successfully in their assigned slots. Price-taking is assumed.

The model is static: it does not adapt after observing gas prices. The binaries
encode indivisible assignments; there are $1\times2\times4\times3\times4=96$
deadline-feasible schedules in this example. Linear costs/constraints plus
binaries make it a MILP. The risk-neutral assignment model has an integral LP
relaxation (also with integer slot capacities); CVaR coupling generally removes
that special structure. Branch-and-bound may be unnecessary on a particular
tiny instance. The notebook explains relaxation, bounds and branching without
implementing a custom solver.

**The Phase 1 milestone stops here.** The now-authorized [Phase 2](docs/phase2.md) defines real
Ethereum Mainnet price measurements and transaction `gas_used`, reproducible
extraction from a provider such as BigQuery or Dune, trajectory construction,
chronological training/test separation, out-of-sample evaluation and baselines.
Deadlines/priorities remain business assumptions. React, FastAPI and Docker
are later demonstration work. No forecasting, database, batching, Layer-2 or MEV
logic is included. Phase 2 adds only the documented Dune/offline data workflow.

Solver interface reference: [Pyomo APPSI result and termination documentation](https://pyomo.readthedocs.io/en/6.9.3/api/pyomo.contrib.appsi.base.Results.html).
