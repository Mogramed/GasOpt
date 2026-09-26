# GasOps Phase 3 — interactive optimization platform

GasOps is the product name; `gasopt` remains the validated Python scientific
package. The platform reads the existing Phase 2 study and never rewrites its
artifacts. No Dune access or API key is used at runtime.

## Launch

From the repository root, with Docker Desktop running:

```powershell
docker compose up --build
```

Open **http://localhost:3000**. For background execution use
`docker compose up --build -d`. Inspect readiness with `docker compose ps`;
both services should become healthy. Stop only this application with
`docker compose down` (the local data files are retained).

The first build downloads packages and images. Subsequent runtime is entirely
offline once those dependencies are cached. Copy `data/processed/` and
`outputs/empirical/` with the repository when moving the demo to another machine;
they are local, gitignored scientific artifacts, not automatically downloaded.

Development, terminal 1, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -c requirements-lock.txt -c requirements-api.txt -e '.[api,dev]'
$env:GASOPS_DEV='1'
.\.venv\Scripts\python.exe -m uvicorn gasopt.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm ci --legacy-peer-deps
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` to port 8000. CORS is enabled
only when `GASOPS_DEV=1`, for the two local Vite origins. The production frontend
uses a same-origin nginx proxy. OpenAPI documentation is at
`http://localhost:8000/docs` in development.

## Architecture and scientific reuse

```text
src/gasopt/                  existing scientific core, unchanged
  api/
    main.py                  application lifespan and versioned routes
    schemas.py               validated request / solve / evaluation contracts
    study.py                 immutable data snapshot and archive consistency audit
    serialization.py         JSON, cost points, schedule identities, UTC labels
    optimization.py          TRAIN-only solver adapter and bounded result cache
    evaluation.py            frozen TEST adapter; no optimizer imports
    education.py             separate tiny pedagogical LP-bound example
frontend/
  src/App.tsx                shell, routing, current-result workspace
  src/api.ts                 API contracts, TanStack Query, formatting
  src/components.tsx         matrix, inspector, heatmap, charts, math, diagnostics
  src/pages/Explore.tsx      overview, data, workload, methodology
  src/pages/Laboratory.tsx   optimization, risk, scenarios, TEST results
  src/pages/Education.tsx    progressive math and branch-and-bound illustration
  src/styles.css            restrained dark interface and responsive layouts
  src/components.test.tsx   React Testing Library / Vitest
  e2e/gasops.spec.ts         live browser demo smoke test
Dockerfile.backend           non-root Python 3.12 / Uvicorn
frontend/Dockerfile          Node build, non-root nginx runtime
frontend/nginx.conf          SPA routes and same-origin API proxy
docker-compose.yml          two services, read-only artifacts, health dependency
tests/test_api.py            API contracts, scientific consistency, regressions
scripts/verify_phase2.py     byte identity check against pre-platform snapshot
```

Unchanged scientific modules include domain types, configuration, baselines,
both Pyomo models, APPSI/HiGHS integration, empirical preparation, study runner,
cost conversion, schedule feasibility, weighted VaR/CVaR, TEST summaries and
savings. The adapters call those functions rather than copying their formulas.
Frontend arithmetic is limited to rendering, formatting, UI parameter support,
and visual color/axis encoding. React does not fit models or compute risk metrics.

At startup, the application validates processed file hashes, matches the archived
configuration and dataset identity, builds the same observed workload, splits
daily trajectories chronologically, and loads the existing CSV outputs. It
re-evaluates the archived schedules with the core to verify displayed TRAIN/TEST
metrics and daily TEST costs. It does not run optimization during startup.
Failure leaves the API unhealthy with an actionable 503 message; no substitute
dataset or fabricated values are loaded.

The TRAIN optimizer accepts only transactions, TRAIN scenarios, configuration
and dataset identity. TEST is not a member of that service. A single lock
serializes HiGHS solves because APPSI's process-level output handling is not
safe for simultaneous in-process calls. The in-memory LRU holds at most 64
results keyed by `(dataset identity, lambda, alpha)`. One worker is used in
Docker. Restarting loads a fresh snapshot and starts an empty cache.

Frozen TEST evaluation invokes `evaluate_schedules` on a copy of the supplied
schedule. Existing core validation checks all transaction IDs and release/deadline
windows. Pydantic additionally rejects noninteger/bool slot assignments, invalid
risk settings and unknown request fields. No evaluation endpoint invokes a solve.

## API

| Method | `/api/v1/` path | Purpose |
|:--|:--|:--|
| GET | `health` | Validated local-study readiness |
| GET | `study/meta` | Counts, dates, config, source, provenance, identity |
| GET | `study/results` | Archived TEST metrics |
| GET | `study/sensitivity` | Prespecified TRAIN grid and distinct schedule IDs |
| GET | `study/archive/{strategy}` | Explicitly labelled archived result |
| GET | `data/slot-profile` | Mean, median, p25, p75 of TRAIN slot medians |
| GET | `data/gas-history?split=TRAIN` | Two-hour prices; TRAIN, TEST or ALL |
| GET | `data/heatmap?split=TRAIN` | Whole daily paths; TRAIN or TEST |
| GET | `data/gas-used` | Candidate histogram and selected observed gas values |
| GET | `workload` | The 30 transactions and feasible windows |
| GET | `model/summary` | Runtime model inputs and mean prices |
| GET | `model/diagnostics` | Archived solver diagnostics |
| POST | `optimization/solve` | Live TRAIN-only solve, `{lambda_risk, alpha}` |
| POST | `evaluation/frozen-schedule` | TEST evaluation, `{schedule, alpha}` |
| GET | `evaluation/daily-costs` | Archived chronological TEST costs |
| POST | `analysis/compare` | Full TRAIN schedules A/B, changed rows and cost differences |
| POST | `analysis/scenario` | One historical day, explicit TRAIN or TEST context |
| POST | `analysis/calculator` | Actual transaction / TRAIN day / feasible slot cost |
| GET | `education/branch-and-bound` | Tiny independent LP-bound illustration |

Solve responses include schedule, binary assignments, cost distribution, objective,
VaR/CVaR, worst cost, status, bound, gap, dimensions and elapsed solve time.
`origin` is `live`, `cached_live` or `archived`; archived values never silently
replace a failed solve. The UI offers an explicit archive button after a failure.
APPSI node count is `null` and is explained in the UI.

Alpha must retain at least the configured 10 TRAIN tail equivalents; the API
returns 422 for too-thin training tails. TEST tails are reported with a visible
warning, including 4.5 equivalents at 95% in this study. Exploratory values outside
the prespecified grid/config are labelled. The UI also records viewing TEST during
the current session and marks subsequent live parameter exploration accordingly.
This is a teaching cue, not a substitute for a preregistered research protocol.

## Routes and live demonstration

`/overview`, `/data`, `/workload`, `/model`, `/optimizer`, `/scenarios`, `/risk`,
`/results`, `/solver`, `/methodology`. No presentation or slide-deck mode exists.

1. Open Optimization Lab; choose Risk neutral, then Run optimization.
2. Choose Light (lambda=.05), run again, and open Compare schedules.
3. Schedule A defaults to archived mean price; B is the current live result.
4. Enable changed-only. There are 11 changed transactions for the validated pair.
5. Click TX-02 to inspect gas, timing, admissible mean prices, old/current slots.
6. Open Risk & CVaR to inspect the sorted TRAIN costs and fractional tail mass.
7. Optionally open TEST results or explicitly evaluate the frozen live schedule.

The comparison selectors also support any pair of archived strategies. Changes,
TRAIN mean/CVaR/worst differences and full-schedule daily costs come from the API.
The inspector explains that CVaR is joint; it does not invent per-transaction
CVaR attribution. The results page can collapse identical schedule regimes.

The SVG heatmap preserves all 12 slots per day, includes hover details and click
selection, and has a keyboard-accessible day selector. A logarithmic color scale
is explicitly labelled. Recharts handles cost/time series, histogram, distributions
and TRAIN frontier. KaTeX renders progressively revealed mathematics, including
the deterministic/expected-value equivalence. Framer Motion is limited to result,
inspector and equation reveals and respects reduced-motion settings.

The branch-and-bound example solves LP relaxations of a separate two-binary
problem (`min 3x+2y`, `2x+2y>=3`). Actual illustrative LP bounds are 3.5 and 4;
the integer optimum is 5. The UI labels it as pedagogical, never as a HiGHS trace.

## Docker and errors

nginx exposes only `127.0.0.1:3000`, proxies `/api` to the private backend, and
serves the built React app. Artifacts are mounted read-only. The frontend waits
for the backend healthcheck; its own `/healthz` verifies HTTP readiness. Both
containers run as non-root users. No credentials are copied to images.

For failures inspect `docker compose logs backend frontend`. Missing artifacts,
hash mismatches and invalid configuration are explicit backend readiness failures.
An API connection failure, invalid solve input, infeasible/error termination or
invalid schedule is shown as an error, never disguised as a successful result.

## Validation commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest-phase3
.\.venv\Scripts\python.exe scripts/verify_phase2.py
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The E2E test expects both development servers to be running. To test Docker:

```powershell
$env:GASOPS_URL='http://localhost:3000'
npm run test:e2e
```

Screenshots are written to `output/playwright/`; failures retain Playwright traces.
API integration tests use the real local archived bundle and explicitly skip if
that bundle is absent. The original synthetic tests still run independently.

## Known scope limits

This is a local single-study demonstrator, not a multi-user service. Results are
not persisted beyond the current session and cache. No authentication, database,
wallet, live trading, forecast, recourse, nonce/dependency handling or inclusion
guarantee is added. Two-hour medians remain execution-price proxies. The 90-day
TEST tail is thin and no statistical-significance or future-savings claim is made.

The initial build requires Internet for packages and images; application use
after setup does not. Code and data must be distributed together for reproducible
offline demonstrations. Browser URLs to external documentation are optional.

Implementation guidance: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
and [Vite setup](https://vite.dev/guide/). All mathematical conclusions and displayed
empirical values come from the local validated scientific core and artifacts.
