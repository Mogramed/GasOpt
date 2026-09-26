# GasOps Phase 3 — completion report

Validation date: 2026-09-25. Product: **GasOps**. Scientific package: **gasopt**.
The local Phase 2 empirical bundle is required; there is no runtime Dune request.

## 1. Final architecture

React/TypeScript browser application → same-origin HTTP API → FastAPI adapters
→ unchanged Pyomo/HiGHS scientific core. The API loads and audits one immutable
local study snapshot. TRAIN fitting and frozen TEST evaluation use separate
adapters. See [architecture and operating guide](platform.md).

## 2. Added files

- `src/gasopt/api/`: `__init__.py`, `main.py`, `schemas.py`, `study.py`,
  `optimization.py`, `evaluation.py`, `serialization.py`, `education.py`.
- `frontend/`: `package.json`, `package-lock.json`, `index.html`, `tsconfig.json`,
  `vite.config.ts`, `playwright.config.ts`, `Dockerfile`, `nginx.conf`.
- `frontend/src/`: `main.tsx`, `App.tsx`, `api.ts`, `components.tsx`, `styles.css`,
  `test-setup.ts`, `components.test.tsx`; `pages/Explore.tsx`,
  `pages/Laboratory.tsx`, `pages/Education.tsx`.
- `frontend/e2e/gasops.spec.ts`, `tests/test_api.py`, `scripts/verify_phase2.py`.
- `Dockerfile.backend`, `docker-compose.yml`, `.dockerignore`,
  `requirements-api.txt`, `docs/platform.md`, `docs/phase3_baseline.json`,
  `docs/phase3_status.md`.
- Generated, gitignored browser captures in `output/playwright/` and frontend
  build output in `frontend/dist/`.

## 3. Modified existing files

`pyproject.toml`: additive API dependency group. `README.md`: platform launch
and documentation links. `.gitignore`: frontend build, dependencies, test
artifacts and screenshots. This inventory is relative to the workspace at the
start of Phase 3; the repository has no tracked baseline commit.

## 4. Scientific modules reused unchanged

`types.py`, `config.py`, `baselines.py`, `empirical_study.py`, `experiment.py`,
`plots.py`; `data/dune.py`, `data/empirical.py`, `data/synthetic.py`;
`models/_common.py`, `models/deterministic.py`, `models/stochastic_cvar.py`;
`evaluation/metrics.py`, `evaluation/out_of_sample.py`.

Cost conversion, schedule feasibility, expected costs, weighted VaR/CVaR,
solver construction and TEST savings come from these existing modules.

## 5. Scientific modules modified

None. The original scientific dependency lock and empirical outputs are retained.
The illustrative branch-and-bound model is new API educational code and never
replaces the empirical optimizer.

## 6. API endpoints

All 19 endpoints use `/api/v1/`:

| Method | Paths |
|:--|:--|
| GET | `health`, `study/meta`, `study/results`, `study/sensitivity`, `study/archive/{strategy}` |
| GET | `data/slot-profile`, `data/gas-history`, `data/heatmap`, `data/gas-used`, `workload` |
| GET | `model/summary`, `model/diagnostics`, `evaluation/daily-costs`, `education/branch-and-bound` |
| POST | `optimization/solve`, `evaluation/frozen-schedule`, `analysis/compare`, `analysis/scenario`, `analysis/calculator` |

Request contracts and endpoint purposes are documented in [platform.md](platform.md#api)
and generated OpenAPI documentation at the development backend's `/docs`.

## 7. Frontend routes

`/overview`, `/data`, `/workload`, `/model`, `/optimizer`, `/scenarios`, `/risk`,
`/results`, `/solver`, `/methodology`.

## 8. Major visualizations

Complete-day gas heatmap with keyboard day selector, historical gas time series,
TRAIN slot mean/median comparison and quantile table, observed gas histogram,
30 × 12 feasible/selected schedule matrix, transaction inspector, paired daily
cost curves, sorted scenario costs with fractional tail highlights, TRAIN
cost–risk frontier, and a separate branch-and-bound tree. Values originate from
the local study; chart interpolation never creates scientific observations.

## 9. Live optimization

Choose lambda and alpha → validate inputs and TRAIN tail support → fit the
unchanged deterministic or CVaR model on TRAIN only → display the actual schedule,
costs and solver diagnostics. A bounded cache is keyed by dataset identity and
parameters. Badges distinguish live, cached live and archived results. A failed
solve displays an error and offers an explicit archived-result button.

## 10. Strategy comparison

Compare any archived pair or an archive against the current workspace result.
The matrix marks previous/current assignments and supports changed-only and
priority filters. The inspector shows observed gas, release/deadline, feasible
slots and mean prices. Full-schedule TRAIN cost differences are calculated by
the core. Lambda 0 versus 0.05 changes **11 transactions**. CVaR differences are
not presented as independent per-transaction contributions.

## 11. CVaR education

Sorted historical costs, VaR and CVaR references, scenario cost/excess/probability
tooltips and fractional boundary tail mass. The prespecified TRAIN grid forms
four distinct schedule regimes. The mathematical page reveals the epigraph and
expected-value/mean-price equivalence. TEST displays a thin-tail warning:
**4.5 scenario equivalents** at 95%, versus 18.25 in TRAIN. Subsequent parameter
exploration after viewing TEST is labelled exploratory within the session.

## 12. Solver education

Actual status, objective, bound, gap, model sizes and elapsed solve time accompany
the empirical result. APPSI does not expose node count here; the UI says so.
The separate two-binary teaching model uses real LP relaxations with bounds
3.5 and 4 and integer optimum 5. It is explicitly not the empirical solve trace.

## 13. Docker architecture

Python 3.12/Uvicorn backend and a Node-built React frontend served by non-root
nginx. Only nginx is published at `127.0.0.1:3000`; it proxies `/api` to the
private backend. Processed data and empirical outputs are mounted read-only.
Both services have HTTP healthchecks. Backend concurrency is one worker with
serialized solver access. No database, account service or credentials are needed.

## 14–17. Validation

| Item | Result |
|:--|:--|
| 14. Python suite | **137 passed**: 94 existing tests and 43 API/regression cases. |
| 15. Frontend | **10 passed** with Vitest/React Testing Library; TypeScript and Vite production build succeeded. |
| 16. Browser E2E | **1 comprehensive test passed** against Docker, 24.8 s total; the earlier development run also passed. |
| 17. Docker | Both images built successfully; both deployed containers are **healthy**; `/api/v1/health` returns `status: ok`. |

The final Chromium run exercised all ten routes, live lambda 0 and 0.05 solves,
the 11-row schedule difference, transaction inspection, frozen live TEST
evaluation, heatmap day selection, workload search, the scenario-cost calculator,
progressive equations, the four risk regimes, TRAIN/TEST scenario views, archived
results, all five educational tree nodes, laptop overflow and an injected 503
with explicit archive fallback. It recorded no browser page errors and **zero
external network requests**, with non-local requests blocked by the test.

Eight screenshots were visually reviewed, including desktop and 1280-pixel
laptop layouts. The initial Docker test exposed an animated-route state reset;
the route location is now fixed to its transition and the final run passes.
Chart tooltips retain series identities, and the CVaR reference label is placed
away from the highest bars. The Python suite emits a non-failing Starlette
deprecation warning; Vite emits the bundle-size advisory described below.

## 18. Exact local development launch

From the repository root, terminal 1:

```powershell
.\.venv\Scripts\python.exe -m pip install -c requirements-lock.txt -c requirements-api.txt -e '.[api,dev]'
$env:GASOPS_DEV='1'
.\.venv\Scripts\python.exe -m uvicorn gasopt.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, from the same repository root:

```powershell
cd frontend
npm ci --legacy-peer-deps
npm run dev
```

## 19. Exact Docker launch

With Docker Desktop running, from the repository root:

```powershell
docker compose up --build -d
docker compose ps
```

Stop with `docker compose down`. This retains local scientific files.

## 20. Browser URLs

Docker: **http://localhost:3000**. Development: **http://localhost:5173**.
The Docker deployment is left running for the demonstration.

## 21. Known limitations

This is a single-study demonstrator. Internet is needed for the initial
package/image build; runtime requests use only the bundled snapshot. The verified
processed data and root empirical tables needed by the API are now versioned for
Vercel; raw extracts and generated figures remain outside Git.
Live results are kept in memory, not in a database. The initial JavaScript bundle
triggers Vite's size advisory; this does not prevent the production build.

Empirical slot medians are execution-price proxies. There is no inclusion
guarantee, nonce/dependency model, forecasting, recourse, live transaction
submission or future savings guarantee. The TEST tail is thin; comparisons are
descriptive and no best lambda is selected from TEST. Session labels do not
replace a preregistered experimental protocol. Browser validation covers desktop
and laptop Chromium, not an exhaustive browser/device matrix.

## 22. Phase 2 numerical preservation

`scripts/verify_phase2.py` checks SHA-256 identity against the pre-platform
manifest: **23/23 files unchanged**, including 14 scientific modules and nine
empirical artifacts. API regressions also compare every prespecified lambda
schedule and recomputed metrics with the archive, including daily TEST costs.

| Frozen strategy | TEST mean (ETH) | TEST CVaR95 (ETH) | Mean savings vs immediate |
|:--|--:|--:|--:|
| Immediate | 0.000418475291 | 0.002673774231 | 0% |
| Mean price / lambda 0 | 0.000299349231 | 0.001928617142 | 28.466689% |
| CVaR lambda 0.05 | 0.000303180581 | 0.001801969364 | 27.551139% |

These displayed values are rounded from the unchanged CSV archive. Neither
schedule fitting nor the prespecified lambda grid uses TEST data.

Phase 3 ends with this platform. No PowerPoint or slide-deck mode was created.
