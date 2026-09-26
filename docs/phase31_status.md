# GasOps Phase 3.1 — Mathematical Deep Dive

Validation date: 2026-09-25. Scope: educational frontend extension only.

## 1. Mathematical sections added

The `/model` route now opens with the business problem and progressively maps
its sentences to sets, parameters, binary decisions, feasible windows, scenario
costs, expectation and CVaR. Nine navigable chapters cover the business problem,
objects and assignment, a numerical scenario coefficient, objective composition,
piecewise-linear CVaR, the complete MILP, matrix form, linear derivatives and
LP versus MILP. A persistent expandable glossary contains the core symbols.

The actual transaction selector exposes one feasible binary row before zooming
out to 30 transactions, 140 admissible decisions and matrices A and P. The
scenario coefficient calculator continues to use the existing read-only API and
local TRAIN data.

## 2. Matrix formulation

The page defines `x ∈ {0,1}^m`, assignment matrix `A` with `Ax = 1`, scenario
coefficient matrix `P`, scenario cost vector `Px` and expected cost `qᵀPx`.
It then forms `z = [x, η, ξ]ᵀ`, the extended linear objective and the CVaR block
`Px − 1η − ξ ≤ 0`. A 3-transaction matrix slice explains the row/column logic.

Dimensions are taken from runtime metadata and archived solver diagnostics:

| Object | Runtime dimension |
|:--|:--|
| x | 140 × 1 |
| P | 365 × 140 |
| q | 365 × 1 |
| A | 30 × 140 |
| ξ | 365 × 1 |
| Positive-lambda model | 506 variables, 395 constraints |

No 365 × 140 payload is transmitted solely for visualization.

## 3. Gradient and Hessian

For the continuous linear relaxation, the page states `f(z)=c_extᵀz`, hence
the gradient is the constant vector `c_ext` and the Hessian is the zero matrix.
A polytope/integer-point diagram explains why the missing curvature does not
remove the combinatorial difficulty. KKT and Newton methods are correctly
described as continuous tools that do not enforce binary integrality.

## 4. CVaR linearization

The pre-epigraph expression displays `max(C_s−η,0)` and its nondifferentiable
kink at `C_s=η`. The inequalities `ξ_s ≥ C_s−η` and `ξ_s ≥ 0` are introduced
with the explanation that minimization forces equality with the positive part.
The complete model remains linear apart from binary domains, hence a MILP.

## 5. Optimality and bounds

The `/solver` route defines the incumbent/upper bound, LP lower bound and
reported relative gap. It shows actual archived/live solver values when
available and does not reconstruct an implementation-specific gap formula.
For minimization it emphasizes `f*_LP ≤ f*_MILP`; the direction is explicit.

## 6. Branch-and-Bound calculations

The original independent teaching problem is retained. Every value is now
derived in the interface:

- root relaxation: `(x,y)=(0.5,1)`, lower bound 3.5;
- branch `x=0`: infeasible because it requires `y≥1.5` while `y≤1`;
- branch `x=1`: `(x,y)=(1,0.5)`, lower bound 4;
- branch `x=1,y=0`: infeasible;
- branch `x=1,y=1`: integer feasible, objective/incumbent 5.

The final certificate explains that all alternatives are closed, so `(1,1)`
with objective 5 is globally optimal. Each tree node exposes fixed variables,
LP solution, lower bound, status, incumbent and pruning reason. The view is
explicitly labelled as pedagogical and not the actual HiGHS execution trace.

## 7. Bound-pruning example

An optional second reveal starts with incumbent 5 and a node whose LP lower
bound is 6. Since `LB_node ≥ UB`, the node is pruned even though infeasibility
has not been shown. This is a deterministic teaching example, not a solver trace.

## 8. Tests added

Five frontend tests cover the complete objective/constraints, dynamic dimensions,
constant gradient, zero Hessian, the absence of a Newton-for-MILP claim, all
five Branch-and-Bound node results and the careful interpretation of `2^140`.
The E2E journey now visits the complete model, matrix, calculus and LP-bound
chapters and checks the pedagogical-trace disclaimer.

## 9. Total validation

| Check | Result |
|:--|:--|
| Python suite | 137 passed |
| Frontend unit/component suite | 15 passed |
| TypeScript + production Vite build | passed |
| Development E2E | 1 comprehensive journey passed |
| Docker build and healthchecks | passed; backend and frontend healthy |
| Production Docker E2E | 1 comprehensive journey passed in 14.6 s |
| Phase 2 byte regression | 23/23 files unchanged |

## 10. Empirical preservation

No backend, optimizer, dataset, schedule, TRAIN/TEST protocol, metric or
empirical artifact was modified. `scripts/verify_phase2.py` confirms SHA-256
identity for all 23 protected scientific modules and empirical outputs.

## 11. Routes and screenshots

New material appears in the existing routes:

- `/model`: business translation, formulation, matrix form, derivatives,
  CVaR linearization, actual coefficient substitution and glossary;
- `/solver`: LP relaxation, actual diagnostics, complete teaching tree,
  bound pruning, terminology, scale and knowledge checks.

Playwright writes the reviewed captures to `output/playwright/`, including
`04-model.png`, `07-solver.png`, `09-complete-model.png` and
`10-matrix-form.png`.

The unconstrained binary space is shown as `2^140 ≈ 1.39 × 10^42` vectors. The
page explicitly says these are not all feasible schedules.

Phase 3.1 adds no optimization model or business functionality.
