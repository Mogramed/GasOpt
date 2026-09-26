import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowDown,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  GitBranch,
} from "lucide-react";
import { useWorkspace } from "../App";
import { api, eth, num, price, useApi, type Tx } from "../api";
import {
  Badge,
  Diagnostics,
  ErrorState,
  Loading,
  MathBlock,
  PageHeader,
  Section,
  Timeline,
} from "../components";

const steps = [
  ["Business problem", "From treasury constraints to one decision"],
  ["Objects & assignment", "Define what the model may choose"],
  ["Scenario coefficient", "Turn gas and price into ETH"],
  ["Expected objective", "Separate expected cost and tail risk"],
  ["CVaR linearization", "Replace a kink with linear inequalities"],
  ["Complete model", "See the whole MILP in one place"],
  ["Matrix form", "From equations to matrices"],
  ["Gradient & Hessian", "Why curvature is not the difficulty"],
  ["LP versus MILP", "Continuous calculus cannot enforce integrality"],
] as const;

const completeModel = String.raw`\begin{aligned}
\min_{x,\eta,\xi}\quad & \sum_{s\in S}q_s C_s(x)
+\lambda\left[\eta+\frac{1}{1-\alpha}\sum_{s\in S}q_s\xi_s\right]\\
\text{s.t.}\quad & \sum_{t:(i,t)\in\mathcal A}x_{it}=1 \quad \forall i\in I\\
& \xi_s\ge C_s(x)-\eta \quad \forall s\in S\\
& \xi_s\ge0 \quad \forall s\in S\\
& x_{it}\in\{0,1\} \quad \forall(i,t)\in\mathcal A\\
& \eta\in\mathbb R,\\[2pt]
& C_s(x)=10^{-9}\sum_{(i,t)\in\mathcal A}g_i p_{ts}x_{it},\\
& \mathcal A=\{(i,t):r_i\le t\le d_i\}.
\end{aligned}`;

export function FullFormulation() {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(completeModel);
      setCopied(true);
      setCopyError(false);
    } catch {
      setCopyError(true);
    }
  };
  return (
    <div className="full-formulation" data-testid="complete-model">
      <div className="formula-header">
        <div>
          <span className="eyebrow">COMPLETE FORMULATION</span>
          <p>One here-and-now schedule, evaluated across every TRAIN path.</p>
        </div>
        <button className="button" onClick={copy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}{" "}
          {copied ? "Copied" : "Copy model"}
        </button>
      </div>
      <MathBlock math={completeModel} />
      <p className="formula-caption" role="status">
        {copyError
          ? "Clipboard unavailable. Select the equation to copy it manually."
          : copied
            ? "Complete LaTeX formulation copied."
            : "One assignment per transaction · scenario tail constraints · binary and continuous domains"}
      </p>
    </div>
  );
}

export function MatrixFormulation({
  transactions,
  scenarios,
  binaries,
  variables,
  constraints,
}: {
  transactions: number;
  scenarios: number;
  binaries: number;
  variables: number;
  constraints: number;
}) {
  return (
    <div className="matrix-explainer" data-testid="matrix-formulation">
      <div
        className="matrix-slice"
        aria-label="Small assignment matrix example"
      >
        <code> </code>
        <code>x₁₁</code>
        <code>x₁₂</code>
        <code>x₂₁</code>
        <code>x₂₂</code>
        <code>x₂₃</code>
        <code>x₃₁</code>
        {[
          ["tx1", 1, 1, 0, 0, 0, 0],
          ["tx2", 0, 0, 1, 1, 1, 0],
          ["tx3", 0, 0, 0, 0, 0, 1],
        ].flatMap((row) =>
          row.map((v, i) => (
            <code className={v === 1 ? "on" : ""} key={`${row[0]}-${i}`}>
              {v}
            </code>
          )),
        )}
      </div>
      <div className="matrix-equations">
        <MathBlock math={String.raw`x\in\{0,1\}^{m},\qquad Ax=\mathbf 1`} />
        <p>
          Each column is one admissible pair (transaction, slot). Each row of A
          collects the columns belonging to one transaction, so Ax = 1 assigns
          it exactly once.
        </p>
        <MathBlock
          math={String.raw`P\in\mathbb R^{S\times m},\quad C(x)=Px,\quad \mathbb E[C]=q^\top Px`}
        />
        <p>
          Row s of P contains cₛⱼ = 10⁻⁹gᵢpₜₛ for decision j ↔ (i,t). P is used
          for scenario costs, avoiding a clash with scalar Cₛ(x).
        </p>
      </div>
      <div className="extended-vector">
        <MathBlock
          math={String.raw`z=\begin{bmatrix}x\\\eta\\\xi\end{bmatrix},\qquad c_{ext}=\begin{bmatrix}P^\top q\\\lambda\\\frac{\lambda}{1-\alpha}q\end{bmatrix},\qquad \min c_{ext}^\top z`}
        />
        <MathBlock
          math={String.raw`Px-\mathbf1\eta-\xi\le0,\qquad Ax=\mathbf1,\qquad x\in\{0,1\}^m,\ \xi\ge0`}
        />
      </div>
      <table className="dimension-table">
        <thead>
          <tr>
            <th>Object</th>
            <th>Dimension</th>
            <th>Empirical value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>x</td>
            <td>m × 1</td>
            <td>{binaries} × 1</td>
          </tr>
          <tr>
            <td>P</td>
            <td>S × m</td>
            <td>
              {scenarios} × {binaries}
            </td>
          </tr>
          <tr>
            <td>q</td>
            <td>S × 1</td>
            <td>{scenarios} × 1</td>
          </tr>
          <tr>
            <td>A</td>
            <td>N × m</td>
            <td>
              {transactions} × {binaries}
            </td>
          </tr>
          <tr>
            <td>ξ</td>
            <td>S × 1</td>
            <td>{scenarios} × 1</td>
          </tr>
        </tbody>
      </table>
      <div className="dimension-summary">
        <span>
          N = <b>{transactions}</b> transactions
        </span>
        <span>
          S = <b>{scenarios}</b> scenarios
        </span>
        <span>
          m = <b>{binaries}</b> binaries
        </span>
        <span>
          positive-λ model = <b>{variables}</b> variables / <b>{constraints}</b>{" "}
          constraints
        </span>
      </div>
    </div>
  );
}

export function LinearRelaxationCalculus() {
  return (
    <div data-testid="linear-calculus">
      <div className="calculus-pair">
        <div>
          <span>Gradient</span>
          <MathBlock
            math={String.raw`f(z)=c_{ext}^{\top}z\quad\Rightarrow\quad\nabla f(z)=c_{ext}`}
          />
          <p>Constant everywhere in the continuous relaxation.</p>
        </div>
        <div>
          <span>Hessian</span>
          <MathBlock math={String.raw`\nabla^2 f(z)=0`} />
          <p>The zero matrix: the objective has no curvature.</p>
        </div>
      </div>
      <RelaxationDiagram />
      <div className="method-comparison">
        <div>
          <span>Continuous nonlinear optimization</span>
          <b>gradient · Hessian · KKT · Newton</b>
        </div>
        <div>
          <span>GasOps MILP</span>
          <b>linear objective · LP relaxation · Branch-and-Bound</b>
        </div>
      </div>
      <p className="explanation">
        KKT conditions can characterize the continuous LP relaxation, but they
        do not impose x ∈ &#123;0,1&#125;ᵐ. Newton or Hessian methods therefore
        do not solve the integer problem.
      </p>
    </div>
  );
}

function RelaxationDiagram() {
  return (
    <figure className="relaxation-figure">
      <svg
        viewBox="0 0 520 250"
        role="img"
        aria-label="Toy problem: the LP feasible triangle includes (0.5, 1); only (1, 1) is integer feasible"
      >
        <path
          d="M55 205H225 M55 205V35 M305 205H475 M305 205V35"
          className="diagram-axis"
        />
        <path d="M55 45H215V205 M305 45H465V205" className="diagram-grid" />
        <path d="M135 45H215V125Z" className="diagram-region" />
        <path
          d="M135 45L215 125 M385 45L465 125"
          className="diagram-boundary"
        />
        <g className="diagram-label">
          <text x="55" y="229">
            0
          </text>
          <text x="210" y="229">
            1
          </text>
          <text x="35" y="49">
            1
          </text>
          <text x="235" y="209">
            x
          </text>
          <text x="51" y="23">
            y
          </text>
          <text x="305" y="229">
            0
          </text>
          <text x="460" y="229">
            1
          </text>
          <text x="285" y="49">
            1
          </text>
          <text x="485" y="209">
            x
          </text>
          <text x="301" y="23">
            y
          </text>
        </g>
        <circle cx="135" cy="45" r="6" className="diagram-fractional" />
        <circle cx="465" cy="45" r="6" className="diagram-integer" />
        <text x="73" y="80" className="diagram-label">
          (0.5, 1)
        </text>
        <text x="407" y="80" className="diagram-label">
          (1, 1)
        </text>
        <text x="262" y="135" textAnchor="middle" className="diagram-label">
          →
        </text>
      </svg>
      <figcaption>
        <div>
          <b>Continuous LP relaxation</b>
          <p>
            Shaded triangle: x + y ≥ 1.5 inside [0, 1]². The fractional optimum
            (0.5, 1) has cost 3.5.
          </p>
        </div>
        <div>
          <b>Binary feasible set</b>
          <p>
            Only (1, 1) satisfies the constraint with binary coordinates. Its
            cost is 5.
          </p>
        </div>
      </figcaption>
    </figure>
  );
}

function PositivePartDiagram() {
  return (
    <figure className="positive-part-figure">
      <svg
        viewBox="0 0 500 230"
        role="img"
        aria-label="Positive part: zero for C_s minus eta below zero, slope one above zero"
      >
        <path d="M35 175H460 M235 202V25" className="diagram-axis" />
        <path d="M40 175H235L375 35" className="diagram-function" />
        <circle cx="235" cy="175" r="5" className="diagram-fractional" />
        <g className="diagram-label">
          <text x="235" y="222" textAnchor="middle">
            0
          </text>
          <text x="440" y="201" textAnchor="middle">
            Cₛ − η
          </text>
          <text x="250" y="28">
            max(Cₛ − η, 0)
          </text>
          <text x="100" y="153">
            No excess
          </text>
          <text x="332" y="117">
            Positive excess
          </text>
        </g>
      </svg>
      <figcaption>
        <b>The kink occurs at Cₛ = η</b>
        <p>
          The slope changes from 0 to 1. Two linear inequalities describe the
          region above this curve.
        </p>
      </figcaption>
    </figure>
  );
}

function Glossary() {
  const items = [
    ["I / T / S", "transactions / slots / historical scenarios"],
    ["𝒜", "admissible transaction-slot pairs"],
    [
      "x / A / P",
      "assignment vector / assignment matrix / scenario-cost matrix",
    ],
    ["r / d", "release slot / deadline slot"],
    ["g / p / q", "gas / prices / scenario probabilities"],
    ["η / ξ", "CVaR threshold / scenario excess"],
    ["α / λ", "confidence / risk weight"],
    ["Cₛ / E[C]", "scenario / expected cost"],
    ["VaR / CVaR", "quantile / average upper-tail cost"],
    ["LB / UB", "global lower bound / incumbent value"],
    ["MIP gap", "distance between bound and incumbent"],
  ];
  return (
    <details className="symbol-glossary">
      <summary>
        Symbol glossary <span>Quick reference</span>
      </summary>
      <dl>
        {items.map(([a, b]) => (
          <div key={a}>
            <dt>{a}</dt>
            <dd>{b}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

export function ModelPage() {
  const { workload, meta, current } = useWorkspace();
  const chapterRef = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0),
    [txId, setTxId] = useState(workload[0].transaction_id),
    [slot, setSlot] = useState(workload[0].release_slot),
    [day, setDay] = useState(meta.config.train_start);
  const tx = workload.find((t) => t.transaction_id === txId)!;
  const heat = useApi<{ dates: string[] }>("data/heatmap");
  const diagnostics =
    useApi<Record<string, number | string | null>[]>("model/diagnostics");
  const positive = diagnostics.data?.find(
    (d) => Number(d.lambda_risk) > 0 && Number(d.num_variables) > 0,
  );
  const calc = useMutation({
    mutationFn: () =>
      api<{
        gas_used: number;
        gas_price_gwei: number;
        conversion: number;
        cost_eth: number;
      }>("analysis/calculator", { transaction_id: txId, day, slot }),
  });
  useEffect(() => {
    if (step === 2) calc.mutate();
  }, [txId, day, slot, step]);
  const go = (n: number) => {
    setStep(n);
    chapterRef.current?.scrollIntoView({ block: "start", behavior: "instant" });
  };
  return (
    <>
      <PageHeader
        eyebrow="03 / MATHEMATICAL DEEP DIVE"
        title="From a treasury decision to a certified optimum"
        description="Translate the business problem into a complete MILP, its matrix form, and the bounds used to prove optimality."
      />
      <div className="problem-statement">
        <div>
          <span>BUSINESS PROBLEM</span>
          <p>
            A crypto treasury must execute each Ethereum transaction exactly
            once within its time window. Gas prices are uncertain. Choose one
            slot per transaction to minimize expected expenditure while
            optionally penalizing high-cost scenarios.
          </p>
        </div>
        <ArrowRight size={18} aria-hidden="true" />
        <div>
          <span>MATHEMATICAL OBJECTS</span>
          <p>
            Transactions, slots, historical price paths, binary assignments and
            a CVaR tail threshold.
          </p>
        </div>
        <ArrowRight size={18} aria-hidden="true" />
        <div>
          <span>OPTIMIZATION MODEL</span>
          <p>
            A mixed-integer linear program: linear costs and constraints, with
            discrete assignment decisions.
          </p>
        </div>
      </div>
      <div className="reading-tools">
        <span>9 chapters · explore in any order</span>
        <Glossary />
      </div>
      <div className="model-layout deep-dive">
        <nav className="model-steps" aria-label="Model steps">
          {steps.map(([title], i) => (
            <button
              key={title}
              className={step === i ? "active" : ""}
              aria-current={step === i ? "step" : undefined}
              onClick={() => go(i)}
            >
              <span>{String(i + 1).padStart(2, "0")}</span>
              {title}
            </button>
          ))}
        </nav>
        <div className="model-content" ref={chapterRef}>
          <div className="chapter-progress" aria-hidden="true">
            <i style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              data-chapter={steps[step][0]}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
            >
              <span className="eyebrow">
                CHAPTER {step + 1} / {steps.length}
              </span>
              <h2>{steps[step][1]}</h2>
              {step === 0 && (
                <div className="translation-lines">
                  <div>
                    <span>Must execute each transaction</span>
                    <ArrowRight />
                    <MathBlock
                      math={String.raw`\sum_{t:(i,t)\in\mathcal A}x_{it}=1`}
                    />
                  </div>
                  <div>
                    <span>Only inside its window</span>
                    <ArrowRight />
                    <MathBlock
                      math={String.raw`\mathcal A=\{(i,t):r_i\le t\le d_i\}`}
                    />
                  </div>
                  <div>
                    <span>Prices are uncertain</span>
                    <ArrowRight />
                    <MathBlock
                      math={String.raw`s\in S,\quad p_{ts},\quad q_s`}
                    />
                  </div>
                  <div>
                    <span>Control the expensive tail</span>
                    <ArrowRight />
                    <MathBlock
                      math={String.raw`\mathbb E[C]+\lambda\operatorname{CVaR}_{\alpha}(C)`}
                    />
                  </div>
                </div>
              )}
              {step === 1 && (
                <>
                  <MathBlock
                    math={String.raw`i\in I,\quad t\in T,\quad s\in S,\qquad x_{it}\in\{0,1\}`}
                  />
                  <p className="model-explanation">
                    Select one observed transaction. Its active cells are
                    exactly the admissible binary variables in that assignment
                    row.
                  </p>
                  <TransactionRow
                    tx={tx}
                    selected={slot}
                    onSelect={setSlot}
                    workload={workload}
                    setTxId={setTxId}
                  />
                  <div className="zoom-out">
                    <span>1 transaction row</span>
                    <ArrowRight />
                    <span>{meta.transaction_count} transactions</span>
                    <ArrowRight />
                    <span>{meta.binary_decisions} admissible x variables</span>
                    <ArrowRight />
                    <span>vector x</span>
                    <ArrowRight />
                    <span>matrices A and P</span>
                  </div>
                </>
              )}
              {step === 2 && (
                <>
                  <MathBlock
                    math={String.raw`c_{its}=10^{-9}g_i p_{ts}\quad[\mathrm{ETH}]`}
                  />
                  <p className="unit-line">
                    <b>gas</b> × <b>gwei / gas</b> × <b>10⁻⁹ ETH / gwei</b> ={" "}
                    <b>ETH</b>
                  </p>
                  <ScenarioPicker
                    tx={tx}
                    workload={workload}
                    setTxId={setTxId}
                    slot={slot}
                    setSlot={setSlot}
                    day={day}
                    setDay={setDay}
                    dates={heat.data?.dates ?? []}
                    calc={calc}
                  />
                </>
              )}
              {step === 3 && (
                <>
                  <div className="objective-blocks">
                    <div>
                      <span>Expected cost</span>
                      <MathBlock math={String.raw`\sum_s q_sC_s(x)`} />
                      <b>{eth(current.expected_cost_eth)} ETH</b>
                    </div>
                    <span>+</span>
                    <div>
                      <span>Risk penalty</span>
                      <MathBlock
                        math={String.raw`\lambda\times\operatorname{CVaR}_{\alpha}`}
                      />
                      <b>
                        {current.lambda_risk} × {eth(current.cvar_eth)} ETH
                      </b>
                    </div>
                    <span>=</span>
                    <div>
                      <span>Total objective</span>
                      <MathBlock
                        math={String.raw`\mathbb E[C]+\lambda\operatorname{CVaR}`}
                      />
                      <b>{eth(current.objective_value_eth)} ETH</b>
                    </div>
                  </div>
                  <p className="explanation">
                    Every objective coefficient begins with 10⁻⁹gᵢpₜₛ.
                    Probabilities qₛ aggregate scenario costs; λ controls the
                    weight placed on the upper tail.
                  </p>
                </>
              )}
              {step === 4 && (
                <>
                  <MathBlock
                    math={String.raw`\operatorname{CVaR}_{\alpha}(C(x))=\min_{\eta}\left[\eta+\frac{1}{1-\alpha}\sum_s q_s\max(C_s(x)-\eta,0)\right]`}
                  />
                  <PositivePartDiagram />
                  <MathBlock
                    math={String.raw`\xi_s\ge C_s(x)-\eta,\qquad\xi_s\ge0`}
                  />
                  <p className="explanation">
                    With positive λ and qₛ, minimization forces ξₛ down to
                    max(Cₛ−η,0). The auxiliary variable replaces the
                    piecewise-linear kink with two linear inequalities, so the
                    final problem remains a MILP. At λ = 0, GasOps uses the
                    risk-neutral model without these auxiliary variables.
                  </p>
                </>
              )}
              {step === 5 && <FullFormulation />}
              {step === 6 &&
                (diagnostics.error ? (
                  <ErrorState error={diagnostics.error} />
                ) : !positive ? (
                  <Loading />
                ) : (
                  <MatrixFormulation
                    transactions={meta.transaction_count}
                    scenarios={meta.train_days}
                    binaries={meta.binary_decisions}
                    variables={Number(positive.num_variables)}
                    constraints={Number(positive.num_constraints)}
                  />
                ))}
              {step === 7 && <LinearRelaxationCalculus />}
              {step === 8 && (
                <>
                  <MathBlock
                    math={String.raw`x_j\in\{0,1\}\quad\longrightarrow\quad0\le x_j\le1`}
                  />
                  <div className="bound-direction">
                    <span>MILP feasible points</span>
                    <b>⊂</b>
                    <span>LP feasible polytope</span>
                    <ArrowRight />
                    <strong>LP optimum ≤ integer optimum</strong>
                  </div>
                  <p className="explanation">
                    For this minimization problem, relaxing integrality enlarges
                    the feasible set. Its optimum is therefore a lower bound.
                    For maximization the direction reverses. Continue to Solver
                    explorer to see every bound calculated by hand.
                  </p>
                  <Link className="button primary inline-action" to="/solver">
                    Open Solver explorer <ArrowRight size={15} />
                  </Link>
                </>
              )}
            </motion.div>
          </AnimatePresence>
          <div className="step-navigation">
            <button
              className="button"
              disabled={step === 0}
              onClick={() => go(step - 1)}
            >
              <ChevronLeft size={16} />
              Previous
            </button>
            <span>
              {step + 1} / {steps.length}
            </span>
            <button
              className="button primary"
              disabled={step === steps.length - 1}
              onClick={() => go(step + 1)}
            >
              Next concept
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

function TransactionRow({
  tx,
  selected,
  onSelect,
  workload,
  setTxId,
}: {
  tx: Tx;
  selected: number;
  onSelect: (n: number) => void;
  workload: Tx[];
  setTxId: (s: string) => void;
}) {
  return (
    <div className="interactive-example">
      <label className="compact-select">
        Actual transaction
        <select
          value={tx.transaction_id}
          onChange={(e) => {
            const next = workload.find(
              (t) => t.transaction_id === e.target.value,
            )!;
            setTxId(next.transaction_id);
            onSelect(next.release_slot);
          }}
        >
          {workload.map((t) => (
            <option key={t.transaction_id}>{t.transaction_id}</option>
          ))}
        </select>
      </label>
      <Timeline tx={tx} selected={selected} onSelect={onSelect} />
      <p className="caption">
        Only slots {tx.release_slot}–{tx.deadline_slot} create columns in x.
        This row contains {tx.window_length} admissible decisions.
      </p>
    </div>
  );
}

type CalcMutation = ReturnType<
  typeof useMutation<
    {
      gas_used: number;
      gas_price_gwei: number;
      conversion: number;
      cost_eth: number;
    },
    Error,
    void
  >
>;
function ScenarioPicker({
  tx,
  workload,
  setTxId,
  slot,
  setSlot,
  day,
  setDay,
  dates,
  calc,
}: {
  tx: Tx;
  workload: Tx[];
  setTxId: (s: string) => void;
  slot: number;
  setSlot: (n: number) => void;
  day: string;
  setDay: (s: string) => void;
  dates: string[];
  calc: CalcMutation;
}) {
  return (
    <div className="interactive-example">
      <div className="toolbar">
        <label>
          Observed transaction
          <select
            value={tx.transaction_id}
            onChange={(e) => {
              const t = workload.find(
                (v) => v.transaction_id === e.target.value,
              )!;
              setTxId(t.transaction_id);
              setSlot(t.release_slot);
            }}
          >
            {workload.map((t) => (
              <option key={t.transaction_id}>{t.transaction_id}</option>
            ))}
          </select>
        </label>
        <label>
          Historical TRAIN scenario
          <select value={day} onChange={(e) => setDay(e.target.value)}>
            {dates.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
      </div>
      <Timeline tx={tx} selected={slot} onSelect={setSlot} />
      {calc.error ? (
        <ErrorState error={calc.error} />
      ) : calc.isPending || !calc.data ? (
        <Loading />
      ) : (
        <div className="calculator">
          <div>
            <span>gᵢ · GAS</span>
            <b>{num(calc.data.gas_used)}</b>
          </div>
          <span>×</span>
          <div>
            <span>pₜₛ · GWEI/GAS</span>
            <b>{price(calc.data.gas_price_gwei)}</b>
          </div>
          <span>× 10⁻⁹ =</span>
          <div>
            <span>cᵢₜₛ · ETH</span>
            <b>{eth(calc.data.cost_eth)}</b>
          </div>
        </div>
      )}
    </div>
  );
}

export type BranchNode = {
  id: string;
  parent: string | null;
  fixed: Record<string, number>;
  bound: number | null;
  x: number | null;
  y: number | null;
  status: string;
  reason: string;
};
type BranchDemo = {
  label: string;
  disclaimer: string;
  formulation: string;
  nodes: BranchNode[];
  optimum: number;
  bound_pruning: string;
};
const nodeMath: Record<
  string,
  { title: string; lines: string[]; incumbent: string; prune: string }
> = {
  root: {
    title: "Root LP relaxation",
    lines: [
      "y costs 2 while x costs 3, so use y first.",
      "y = 1 ⇒ x + 1 ≥ 1.5 ⇒ x ≥ 0.5",
      "3(0.5) + 2(1) = 3.5",
    ],
    incumbent: "not found",
    prune: "Branch on fractional x = 0.5",
  },
  x0: {
    title: "Node A · x = 0",
    lines: ["0 + y ≥ 1.5 ⇒ y ≥ 1.5", "But the relaxation requires y ≤ 1."],
    incumbent: "not found",
    prune: "Prune by infeasibility",
  },
  x1: {
    title: "Node B · x = 1",
    lines: ["1 + y ≥ 1.5 ⇒ y ≥ 0.5", "3(1) + 2(0.5) = 4"],
    incumbent: "not found",
    prune: "Branch on fractional y = 0.5",
  },
  y0: {
    title: "Node B1 · x = 1, y = 0",
    lines: ["1 + 0 ≥ 1.5 is false."],
    incumbent: "not found",
    prune: "Prune by infeasibility",
  },
  y1: {
    title: "Node B2 · x = 1, y = 1",
    lines: ["1 + 1 ≥ 1.5 is true.", "3(1) + 2(1) = 5"],
    incumbent: "UB = 5",
    prune: "Integer feasible: update incumbent",
  },
};

export function BranchWalkthrough({
  nodes,
  depth,
  selected,
  onSelect,
}: {
  nodes: BranchNode[];
  depth: number;
  selected: string;
  onSelect: (s: string) => void;
}) {
  const active = nodes.find((n) => n.id === selected) ?? nodes[0],
    note = nodeMath[active.id];
  return (
    <div className="branch-layout" data-testid="branch-walkthrough">
      <div className="branch-tree">
        {[nodes.slice(0, 1), nodes.slice(1, 3), nodes.slice(3)]
          .slice(0, depth + 1)
          .map((level, i) => (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              key={i}
              className={`branch-level level-${i}`}
            >
              {level.map((n) => (
                <button
                  onClick={() => onSelect(n.id)}
                  aria-pressed={selected === n.id}
                  key={n.id}
                  className={`branch-node ${n.bound === null ? "pruned" : ""} ${selected === n.id ? "active" : ""}`}
                >
                  <span>
                    {n.id === "root"
                      ? "ROOT"
                      : Object.entries(n.fixed)
                          .map(([k, v]) => `${k} = ${v}`)
                          .join(", ")}
                  </span>
                  <b>
                    {n.bound === null
                      ? "INFEASIBLE"
                      : `LB = ${n.bound.toFixed(1)}`}
                  </b>
                  <small>{n.x === null ? "PRUNE" : `x=${n.x}, y=${n.y}`}</small>
                  <em>{n.status}</em>
                </button>
              ))}
            </motion.div>
          ))}
      </div>
      <aside className="node-inspector">
        <Badge>{active.status}</Badge>
        <h3>{note.title}</h3>
        <ol>
          {note.lines.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ol>
        <dl>
          <dt>LP lower bound</dt>
          <dd>{active.bound ?? "—"}</dd>
          <dt>LP solution</dt>
          <dd>{active.x === null ? "—" : `(${active.x}, ${active.y})`}</dd>
          <dt>Incumbent</dt>
          <dd>{note.incumbent}</dd>
        </dl>
        <strong>{note.prune}</strong>
      </aside>
    </div>
  );
}

export function SearchSpaceNote({ binaries }: { binaries: number }) {
  const approx = (2 ** binaries).toExponential(2).replace("e+", " × 10^");
  return (
    <div className="scale-note" data-testid="search-space">
      <span>UNCONSTRAINED BINARY SEARCH SPACE</span>
      <b>
        2<sup>{binaries}</sup> ≈ {approx}
      </b>
      <p>
        This counts all binary vectors, not feasible schedules. Assignment
        constraints eliminate many vectors, but brute-force enumeration is still
        not a serious solution method.
      </p>
    </div>
  );
}

function BoundPruningExample() {
  const [open, setOpen] = useState(false);
  return (
    <div className="bound-example">
      <div>
        <span>OPTIONAL SECOND EXAMPLE</span>
        <h3>Prune by bound</h3>
        <p>
          An incumbent with value 5 already exists. Another minimization node
          has LP lower bound 6.
        </p>
      </div>
      <button className="button" onClick={() => setOpen(!open)}>
        {open ? "Hide conclusion" : "Check the bound"}
      </button>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bound-verdict"
        >
          <MathBlock math={String.raw`LB_{node}=6\ge UB=5`} />
          <b>PRUNE</b>
          <p>
            Every integer solution inside that node costs at least 6, so none
            can improve the incumbent 5.
          </p>
        </motion.div>
      )}
    </div>
  );
}
function KnowledgeCheck() {
  const [shown, setShown] = useState<Record<number, boolean>>({});
  const qs = [
    [
      "If the LP relaxation gives 4.2 and the best integer solution is 5, which is the lower bound?",
      "4.2. For minimization, the relaxed optimum is the lower bound.",
    ],
    [
      "What happens when a node has LB = 6 and incumbent UB = 5?",
      "Prune it by bound: it cannot contain a better solution.",
    ],
    [
      "Why may x = 0.5 appear in the relaxation?",
      "The relaxation replaces x ∈ {0,1} with 0 ≤ x ≤ 1.",
    ],
  ];
  return (
    <div className="knowledge-check">
      {qs.map(([q, a], i) => (
        <div key={q}>
          <p>{q}</p>
          <button onClick={() => setShown({ ...shown, [i]: !shown[i] })}>
            {shown[i] ? a : "Reveal answer"}
          </button>
        </div>
      ))}
    </div>
  );
}

export function SolverPage() {
  const { current, meta } = useWorkspace();
  const demo = useApi<BranchDemo>("education/branch-and-bound");
  const [selected, setSelected] = useState("root"),
    [depth, setDepth] = useState(0);
  const terms = [
    ["Node", "Subproblem formed by fixing integer variables."],
    ["Relaxation", "Continuous version used to calculate a bound."],
    [
      "Lower bound",
      "For minimization, the best value a relaxed node could promise.",
    ],
    [
      "Incumbent",
      "Best integer feasible solution found so far; its value is the upper bound.",
    ],
    ["Branch", "Split one fractional integer decision into separate cases."],
    ["Prune by infeasibility", "Close a node with no feasible solution."],
    ["Prune by bound", "Close a node that cannot beat the incumbent."],
    [
      "Prune by integrality",
      "Close a relaxed node whose optimum is already integer.",
    ],
    [
      "Optimality gap",
      "Distance between the global lower bound and incumbent.",
    ],
  ];
  return (
    <>
      <PageHeader
        eyebrow="08 / OPTIMIZATION MECHANICS"
        title="How a solver proves optimality"
        description="Follow LP bounds, branching, incumbents and pruning from a two-variable problem to the empirical GasOps MILP."
      />
      <Section
        title="The central relaxation"
        subtitle="A lower bound for this minimization problem"
      >
        <div className="relaxation-banner">
          <MathBlock
            math={String.raw`x_j\in\{0,1\}\quad\longrightarrow\quad0\le x_j\le1`}
          />
          <p>
            The relaxed feasible set is larger, so its minimum can only be lower
            than or equal to the integer minimum.
          </p>
          <MathBlock
            math={String.raw`f^*_{LP}\le f^*_{MILP}\qquad\text{(minimization)}`}
          />
        </div>
      </Section>
      <Section
        title="Current empirical result"
        subtitle={`λ = ${current.lambda_risk} · α = ${current.alpha} · ${current.origin === "archived" ? "validated archive" : "live engine result"}`}
      >
        <Diagnostics r={current} />
        <div className="optimality-strip">
          <div>
            <span>Incumbent / upper bound</span>
            <b>{eth(current.objective_value_eth)} ETH</b>
          </div>
          <div>
            <span>Solver lower bound</span>
            <b>{eth(current.objective_bound_eth)} ETH</b>
          </div>
          <div>
            <span>Reported relative gap</span>
            <b>
              {current.optimality_gap == null
                ? "—"
                : current.optimality_gap.toExponential(2)}
            </b>
          </div>
        </div>
        <p className="caption">
          At optimality, the lower and upper bounds agree within solver
          tolerance. The displayed gap is the solver result; GasOps does not
          substitute an implementation-specific formula.
        </p>
      </Section>
      <Section
        title="Branch-and-Bound, calculated line by line"
        subtitle="Pedagogical example — not the actual HiGHS execution trace of the empirical model."
      >
        {demo.error ? (
          <ErrorState error={demo.error} />
        ) : !demo.data ? (
          <Loading />
        ) : (
          <>
            <MathBlock
              math={String.raw`\min\ 3x+2y\quad\text{s.t. }x+y\ge1.5,\quad x,y\in\{0,1\}`}
            />
            <div className="root-derivation">
              <span>ROOT LP</span>
              <p>y is cheaper (2 versus 3), so set y = 1 first.</p>
              <MathBlock math={String.raw`x+1\ge1.5\Rightarrow x\ge0.5`} />
              <MathBlock
                math={String.raw`x=0.5,\ y=1\Rightarrow3(0.5)+2(1)=3.5`}
              />
              <b>ROOT LOWER BOUND = 3.5</b>
            </div>
            <div className="toolbar">
              <button
                className="button"
                disabled={depth === 0}
                onClick={() => {
                  setDepth(depth - 1);
                  setSelected("root");
                }}
              >
                Previous level
              </button>
              <button
                className="button primary"
                disabled={depth === 2}
                onClick={() => setDepth(depth + 1)}
              >
                Reveal branch <GitBranch size={15} />
              </button>
              <span className="caption">Level {depth} / 2</span>
            </div>
            <BranchWalkthrough
              nodes={demo.data.nodes}
              depth={depth}
              selected={selected}
              onSelect={setSelected}
            />
            {depth === 2 && (
              <div className="certificate">
                <span>GLOBAL CERTIFICATE</span>
                <MathBlock math={String.raw`x^*=1,\quad y^*=1,\quad f^*=5`} />
                <p>
                  All other branches are infeasible or closed. No unexplored
                  node has a lower bound below 5. Branch-and-Bound has proved
                  that no better integer solution exists.
                </p>
              </div>
            )}
          </>
        )}
      </Section>
      <Section
        title="A second pruning mechanism"
        subtitle="A node may be feasible and still be useless"
      >
        <BoundPruningExample />
      </Section>
      <Section
        title="Branch-and-Bound vocabulary"
        subtitle="The terms used in solver diagnostics"
      >
        <div className="term-grid">
          {terms.map(([a, b]) => (
            <div key={a}>
              <b>{a}</b>
              <p>{b}</p>
            </div>
          ))}
        </div>
      </Section>
      <Section
        title="The same logic at empirical scale"
        subtitle="The teaching tree explains the concept, not the production trace"
      >
        <div className="scale-comparison">
          <div>
            <span>TOY</span>
            <b>2</b>
            <p>binary variables</p>
          </div>
          <ArrowRight />
          <div>
            <span>GASOPS</span>
            <b>{meta.binary_decisions}</b>
            <p>binaries · {meta.train_days} scenarios · CVaR auxiliaries</p>
          </div>
        </div>
        <SearchSpaceNote binaries={meta.binary_decisions} />
        <div className="solver-pipeline">
          {[
            "Business inputs",
            "MILP formulation",
            "LP relaxation",
            "Branch & bound",
            "Integer candidate",
            "Bound comparison",
            "Optimality gap",
            "Certified optimum",
            "Schedule",
          ].map((x, i) => (
            <div key={x}>
              <span>{String(i + 1).padStart(2, "0")}</span>
              <b>{x}</b>
              {i < 8 && <ArrowRight size={14} />}
            </div>
          ))}
        </div>
        <div className="evaluation-pipeline">
          <b>Schedule</b>
          <ArrowRight />
          <span>TRAIN distribution</span>
          <ArrowRight />
          <span>Expected cost / VaR / CVaR</span>
          <ArrowRight />
          <span>Frozen TEST evaluation</span>
        </div>
      </Section>
      <Section
        title="Check your understanding"
        subtitle="Three short checks; answers stay on this page"
      >
        <KnowledgeCheck />
      </Section>
    </>
  );
}
