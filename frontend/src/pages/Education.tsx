import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
} from "lucide-react";
import { useWorkspace } from "../App";
import { api, eth, num, price, useApi, type Tx } from "../api";
import {
  Badge,
  ErrorState,
  Loading,
  MathBlock,
  PageHeader,
  ScheduleMatrix,
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
                    For maximization the direction reverses. Run the optimizer,
                    then open Calculation trace to inspect the real HiGHS bound,
                    gap and node count.
                  </p>
                  <Link className="button primary inline-action" to="/solver">
                    Open Calculation trace <ArrowRight size={15} />
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

export function SolverPage() {
  const { calculation, workload } = useWorkspace();
  const [allScenarios, setAllScenarios] = useState(false);

  if (!calculation) {
    return (
      <>
        <PageHeader
          eyebrow="08 / CALCULATION TRACE"
          title="No calculation to explain yet"
          description="Run the portfolio optimizer first. This page will then reconstruct every numerical step from that exact HiGHS result."
        />
        <div className="trace-empty">
          <span>WAITING FOR A LIVE SOLVE</span>
          <h2>The trace starts when the calculation starts</h2>
          <p>
            Archived schedules remain available elsewhere as references. This
            page only explains a result produced from the calculator in the
            current session.
          </p>
          <Link className="button primary" to="/optimizer">
            Open Optimization lab <ArrowRight size={15} />
          </Link>
        </div>
      </>
    );
  }

  const trace = calculation.calculation_trace;
  const tail = calculation.scenario_costs
    .filter((point) => point.tail_mass > 0)
    .sort((a, b) => b.cost_eth - a.cost_eth);
  const scenarios = [...calculation.scenario_costs].sort(
    (a, b) => b.cost_eth - a.cost_eth,
  );
  const coefficient = trace.coefficient_example;
  const risk = trace.risk;
  const objective = trace.objective;
  const solver = trace.solver;

  return (
    <>
      <PageHeader
        eyebrow="08 / CALCULATION TRACE"
        title="One solve, reconstructed from inputs to certificate"
        description="Every value below comes from the current GasOps portfolio and the audited HiGHS response."
        action={
          <Badge tone="green">
            LIVE · {solver.status.toUpperCase()} · {trace.solution.schedule_id}
          </Badge>
        }
      />

      <nav className="trace-index" aria-label="Calculation steps">
        {[
          "Inputs",
          "MILP",
          "Coefficient",
          "Scenarios",
          "CVaR",
          "Objective",
          "Certificate",
          "Schedule",
        ].map((label, index) => (
          <a key={label} href={"#trace-" + (index + 1)}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {label}
          </a>
        ))}
      </nav>

      <Section
        title="1 · Inputs fixed before optimization"
        subtitle="The schedule is chosen once and evaluated across all TRAIN days"
      >
        <div className="trace-metrics" id="trace-1">
          <div><span>Transactions</span><b>{trace.inputs.transactions}</b></div>
          <div><span>TRAIN scenarios</span><b>{trace.inputs.train_scenarios}</b></div>
          <div><span>Two-hour slots</span><b>{trace.inputs.slots}</b></div>
          <div><span>Scenario probability</span><b>{trace.inputs.scenario_probability.toFixed(6)}</b></div>
          <div><span>Risk weight λ</span><b>{trace.inputs.lambda_risk}</b></div>
          <div><span>Confidence α</span><b>{trace.inputs.alpha}</b></div>
        </div>
        <MathBlock
          math={String.raw`q_s=1/${trace.inputs.train_scenarios},\qquad (1-\alpha)|S|=${trace.inputs.tail_scenario_equivalents.toFixed(2)}\text{ scenario equivalents}`}
        />
      </Section>

      <Section
        title="2 · Portfolio constraints become one MILP"
        subtitle="Only transaction-slot pairs inside their business windows exist as binary decisions"
      >
        <div className="trace-equation-row" id="trace-2">
          <MathBlock
            math={String.raw`x_{it}\in\{0,1\},\qquad \sum_{t=r_i}^{d_i}x_{it}=1\quad\forall i`}
          />
          <ArrowRight aria-hidden="true" />
          <div className="trace-count">
            <b>{trace.model.total_variables}</b>
            <span>variables</span>
            <small>
              {trace.model.binary_variables} binary +{" "}
              {trace.model.continuous_variables} continuous
            </small>
          </div>
          <div className="trace-count">
            <b>{trace.model.total_constraints}</b>
            <span>constraints</span>
            <small>
              {trace.model.assignment_constraints} assignment +{" "}
              {trace.model.excess_constraints} CVaR
            </small>
          </div>
        </div>
        <p className="explanation">
          The {trace.model.binary_variables} admissible cells are the actual
          decision vector. Forbidden slots are omitted, so they cannot be
          selected by the solver.
        </p>
      </Section>

      <Section
        title="3 · One real cost coefficient"
        subtitle={`${coefficient.transaction_id} · worst-cost TRAIN scenario ${coefficient.scenario_date} · selected slot ${coefficient.selected_slot}`}
      >
        <div className="coefficient-worked" id="trace-3">
          <MathBlock math={String.raw`c_{its}=10^{-9}g_i p_{ts}`} />
          <div>
            <span>{num(coefficient.gas_used)} gas</span>
            <b>×</b>
            <span>{price(coefficient.gas_price_gwei)} gwei / gas</span>
            <b>×</b>
            <span>10⁻⁹ ETH / gwei</span>
            <b>=</b>
            <strong>{eth(coefficient.coefficient_eth)} ETH</strong>
          </div>
        </div>
        <p className="formula-caption">
          This is one transaction’s contribution. Summing the 30 selected
          coefficients gives {eth(coefficient.portfolio_cost_eth)} ETH for this
          complete historical scenario.
        </p>
      </Section>

      <Section
        title="4 · The schedule generates 365 scenario costs"
        subtitle="Expected cost is the probability-weighted average of the same fixed schedule"
      >
        <div className="expectation-worked" id="trace-4">
          <MathBlock
            math={String.raw`C_s(x)=10^{-9}\sum_i\sum_t g_i p_{ts}x_{it}`}
          />
          <ArrowRight aria-hidden="true" />
          <MathBlock
            math={String.raw`\mathbb E[C(x)]=\sum_s q_sC_s(x)=${objective.expected_cost_eth.toFixed(9)}\ \mathrm{ETH}`}
          />
        </div>
        <p className="explanation">
          Gas use and assignments are fixed. Only the historical slot-price
          path changes from one TRAIN day to another.
        </p>
      </Section>

      <Section
        title="5 · CVaR isolates the expensive tail"
        subtitle={
          risk.in_objective
            ? "The tail term participates directly in this optimization."
            : "λ = 0: VaR and CVaR are evaluated after the solve and do not affect the objective."
        }
      >
        <div className="cvar-worked" id="trace-5">
          <MathBlock
            math={String.raw`\xi_s=\max(C_s-\eta,0),\qquad \operatorname{CVaR}_\alpha=\eta+\frac{\sum_s q_s\xi_s}{1-\alpha}`}
          />
          <div className="substitution">
            <span>η = {eth(risk.eta_eth)}</span>
            <span>Σ qₛξₛ = {eth(risk.weighted_excess_eth)}</span>
            <span>1 / (1 − α) = {risk.tail_multiplier.toFixed(2)}</span>
            <strong>CVaR = {eth(risk.cvar_eth)} ETH</strong>
          </div>
        </div>
        <p className="formula-caption">
          {risk.positive_excess_scenarios} scenarios lie strictly above η. The
          fractional boundary mass is retained, so the displayed tail mass is
          exactly {(1 - calculation.alpha).toFixed(2)}.
        </p>
        <div className="table-scroll">
          <table aria-label="CVaR tail scenarios">
            <thead>
              <tr>
                <th>TRAIN day</th>
                <th>Cₛ(x) ETH</th>
                <th>η ETH</th>
                <th>ξₛ ETH</th>
                <th>Tail mass</th>
              </tr>
            </thead>
            <tbody>
              {tail.map((point) => (
                <tr key={point.date}>
                  <td>{point.date}</td>
                  <td>{eth(point.cost_eth)}</td>
                  <td>{eth(point.eta_eth)}</td>
                  <td>{eth(point.xi_eth)}</td>
                  <td>{point.tail_mass.toFixed(6)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button className="button scenario-toggle" onClick={() => setAllScenarios(!allScenarios)}>
          {allScenarios ? "Hide all scenario outputs" : "Show all 365 scenario outputs"}
        </button>
        {allScenarios && (
          <motion.div
            className="table-scroll full-scenario-table"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <table aria-label="All TRAIN scenario outputs">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>TRAIN day</th>
                  <th>Cost ETH</th>
                  <th>Excess ξₛ</th>
                  <th>Cumulative probability</th>
                </tr>
              </thead>
              <tbody>
                {scenarios.map((point) => (
                  <tr key={point.date}>
                    <td>{point.rank}</td>
                    <td>{point.date}</td>
                    <td>{eth(point.cost_eth)}</td>
                    <td>{eth(point.xi_eth)}</td>
                    <td>{point.cumulative_probability.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </motion.div>
        )}
      </Section>

      <Section
        title="6 · Numerical objective"
        subtitle="The solver minimizes expected expenditure plus the selected price of tail risk"
      >
        <div className="objective-substitution" id="trace-6">
          <MathBlock
            math={String.raw`\min\;\mathbb E[C]+\lambda\operatorname{CVaR}_\alpha(C)`}
          />
          <div>
            <span>{eth(objective.expected_cost_eth)}</span>
            <b>+</b>
            <span>{calculation.lambda_risk} × {eth(calculation.cvar_eth)}</span>
            <b>=</b>
            <strong>{eth(objective.objective_value_eth)} ETH</strong>
          </div>
        </div>
      </Section>

      <Section
        title="7 · HiGHS optimality certificate"
        subtitle="Branch-and-Bound is reported from the real solve, without a fabricated teaching tree"
      >
        <div className="certificate-live" id="trace-7">
          <div><span>Status</span><b>{solver.status}</b></div>
          <div><span>Incumbent</span><b>{eth(objective.objective_value_eth)} ETH</b></div>
          <div><span>Global bound</span><b>{eth(solver.objective_bound_eth)} ETH</b></div>
          <div><span>Relative gap</span><b>{solver.optimality_gap == null ? "—" : solver.optimality_gap.toExponential(2)}</b></div>
          <div><span>B&B nodes</span><b>{solver.node_count ?? "—"}</b></div>
          <div><span>Solve time</span><b>{solver.solve_seconds == null ? "—" : solver.solve_seconds.toFixed(3) + " s"}</b></div>
        </div>
        <p className="explanation">
          {solver.node_count != null && solver.node_count <= 1
            ? "HiGHS certified this optimum at the root node. Presolve, the LP relaxation and the solver’s cuts closed the bound without requiring a visible branch tree."
            : solver.node_count != null && solver.node_count > 1
              ? `HiGHS explored ${solver.node_count} Branch-and-Bound nodes before the incumbent and global lower bound met at the reported tolerance.`
              : "The solver returned an optimal certificate, but this runtime did not expose a node count."}
        </p>
        <MathBlock
          math={String.raw`LB=${solver.objective_bound_eth == null ? "\text{not exposed}" : solver.objective_bound_eth.toFixed(9)},\qquad UB=${objective.objective_value_eth.toFixed(9)},\qquad gap=${solver.optimality_gap == null ? "\text{not exposed}" : solver.optimality_gap.toExponential(2)}`}
        />
      </Section>

      <Section
        title="8 · Optimal execution schedule"
        subtitle={`${trace.solution.assignment_count} transactions assigned once · ${trace.solution.changed_vs_mean_price} changed versus mean-price`}
      >
        <div id="trace-8">
          <ScheduleMatrix
            workload={workload}
            schedule={calculation.schedule}
            onSelect={() => undefined}
          />
        </div>
        <div className="trace-final">
          <span>Schedule ID</span>
          <code>{trace.solution.schedule_id}</code>
          <Link className="button" to="/optimizer">
            Return to calculator <ArrowRight size={15} />
          </Link>
        </div>
      </Section>
    </>
  );
}
