import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Play,
  ArrowRight,
  ArrowUpRight,
  GitCompareArrows,
  RotateCcw,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  ScatterChart,
  Scatter,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from "recharts";
import { useWorkspace } from "../App";
import {
  api,
  useApi,
  eth,
  price,
  num,
  label,
  type Result,
  type Tx,
  type Compare,
  type Sensitivity,
  type Evaluation,
  type MetricRow,
  type HeatData,
} from "../api";
import {
  PageHeader,
  Section,
  Metric,
  Loading,
  ErrorState,
  ScheduleMatrix,
  Inspector,
  Badge,
  ResultMetrics,
  Diagnostics,
  CostDistribution,
  PathChart,
  TestBanner,
  MathBlock,
  tooltipStyle,
} from "../components";

export function LambdaControl({
  value,
  onChange,
}: {
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <div className="presets">
      {[
        [0, "Risk neutral"],
        [0.05, "Light"],
        [0.5, "Moderate"],
        [1, "Strong"],
      ].map(([n, t]) => (
        <button
          key={n}
          className={value === n ? "active" : ""}
          onClick={() => onChange(Number(n))}
        >
          <span>{t}</span>
          <b>λ = {n}</b>
        </button>
      ))}
    </div>
  );
}
function ArchiveSelector({
  value,
  onChange,
  includeCurrent = false,
}: {
  value: string;
  onChange: (s: string) => void;
  includeCurrent?: boolean;
}) {
  const { meta } = useWorkspace();
  return (
    <select
      aria-label="Strategy"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {includeCurrent && (
        <option value="current">Current workspace result</option>
      )}
      <option value="immediate">Immediate</option>
      <option value="mean_price">Mean price</option>
      {meta.config.lambda_grid.map((n) => (
        <option key={n} value={"cvar_lambda_" + n}>
          CVaR λ = {n}
        </option>
      ))}
    </select>
  );
}
export function Origin({ r }: { r: Result }) {
  return (
    <Badge tone={r.origin === "archived" ? "neutral" : "green"}>
      {r.origin === "archived"
        ? "Validated Phase 2 archive"
        : r.origin === "cached_live"
          ? "Cached live solve"
          : "Live solve"}{" "}
      · {r.solver_status}
    </Badge>
  );
}

export function Optimizer() {
  const {
    meta,
    workload,
    profile,
    current,
    setCurrent,
    mean,
    viewedTest,
    markTest,
  } = useWorkspace();
  const [risk, setRisk] = useState(current.lambda_risk),
    [alpha, setAlpha] = useState(current.alpha),
    [compare, setCompare] = useState(false),
    [aName, setAName] = useState("mean_price"),
    [bName, setBName] = useState("current"),
    [onlyChanged, setOnlyChanged] = useState(false),
    [priority, setPriority] = useState("ALL"),
    [selected, setSelected] = useState<Tx | null>(null);
  const a = useApi<Result>("study/archive/" + aName, compare),
    b = useApi<Result>(
      "study/archive/" + bName,
      compare && bName !== "current",
    );
  const right = bName === "current" ? current : b.data;
  const comparison = useMutation({
    mutationFn: (v: { a: Result; b: Result }) =>
      api<Compare>("analysis/compare", {
        schedule_a: v.a.schedule,
        schedule_b: v.b.schedule,
        alpha: current.alpha,
      }),
  });
  useEffect(() => {
    if (compare && a.data && right) comparison.mutate({ a: a.data, b: right });
  }, [compare, a.data, right, current.alpha]);
  const solve = useMutation({
    mutationFn: () =>
      api<Result>("optimization/solve", { lambda_risk: risk, alpha }),
    onSuccess: (r) => {
      setCurrent({ ...r, exploratory: r.exploratory || viewedTest });
      setBName("current");
    },
  });
  const evaluation = useMutation({
    mutationFn: () =>
      api<Evaluation>("evaluation/frozen-schedule", {
        schedule: current.schedule,
        alpha: current.alpha,
      }),
    onMutate: markTest,
  });
  const fallback = useMutation({
    mutationFn: () => api<Result>("study/archive/cvar_lambda_" + risk),
    onSuccess: setCurrent,
  });
  const tail = (1 - alpha) * meta.train_days,
    invalid =
      !Number.isFinite(risk) ||
      risk < 0 ||
      !Number.isFinite(alpha) ||
      alpha <= 0 ||
      alpha >= 1 ||
      tail + 1e-12 < meta.config.min_train_tail_count;
  const displayed = compare && right ? right : current,
    baseline = compare ? a.data : undefined;
  return (
    <>
      <PageHeader
        eyebrow="04 / DECISION WORKSPACE"
        title="Optimization lab"
        description="Choose a risk-aversion weight. Fit on TRAIN. Inspect the resulting schedule."
        action={<Badge>TRAIN ONLY · {meta.train_days} SCENARIOS</Badge>}
      />
      <div className="lab-controls">
        <div>
          <span className="control-label">RISK-AVERSION PRESETS</span>
          <LambdaControl value={risk} onChange={setRisk} />
        </div>
        <label>
          Custom λ
          <input
            aria-label="Lambda"
            type="number"
            min="0"
            step="0.05"
            value={Number.isNaN(risk) ? "" : risk}
            onChange={(e) =>
              setRisk(e.target.value === "" ? NaN : Number(e.target.value))
            }
          />
        </label>
        <label>
          Confidence α
          <input
            aria-label="Alpha"
            type="number"
            min="0.01"
            max="0.9999"
            step="0.01"
            value={Number.isNaN(alpha) ? "" : alpha}
            onChange={(e) =>
              setAlpha(e.target.value === "" ? NaN : Number(e.target.value))
            }
          />
        </label>
        <button
          className="button primary run-button"
          disabled={solve.isPending || invalid}
          onClick={() => {
            evaluation.reset();
            solve.mutate();
          }}
        >
          <Play size={16} />
          {solve.isPending ? "Solving on TRAIN…" : "Run optimization"}
        </button>
      </div>
      <div className="control-foot">
        <span>
          TRAIN tail support{" "}
          <b>{Number.isFinite(tail) ? tail.toFixed(2) : "—"}</b> scenario
          equivalents
        </span>
        <span>λ weights risk; α defines the tail threshold.</span>
      </div>
      {invalid && (
        <div className="notice">
          Enter λ ≥ 0 and 0 &lt; α &lt; 1. Keep at least{" "}
          {meta.config.min_train_tail_count} TRAIN tail equivalents; lower α if
          the tail is thin.
        </div>
      )}
      {(viewedTest ||
        !meta.config.lambda_grid.includes(risk) ||
        alpha !== meta.alpha) && (
        <div className="notice">
          Exploratory what-if — parameter experimentation after viewing TEST, or
          outside the pre-specified grid. Do not choose λ from TEST performance.
        </div>
      )}
      {solve.isPending && (
        <Loading text="Pyomo / HiGHS is solving the TRAIN model. Waiting for actual solver completion…" />
      )}
      {solve.error && (
        <>
          <ErrorState error={solve.error} />
          {meta.config.lambda_grid.includes(risk) && (
            <button className="button" onClick={() => fallback.mutate()}>
              View validated Phase 2 result at α = {meta.alpha}
            </button>
          )}
          {fallback.error && <ErrorState error={fallback.error} />}
        </>
      )}
      <div className="result-top">
        <Origin r={current} />
        <span>
          λ = {current.lambda_risk} · α = {current.alpha} · schedule{" "}
          <code>{current.schedule_id}</code>
        </span>
      </div>
      <motion.div
        key={current.schedule_id + current.origin}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <ResultMetrics r={current} />
      </motion.div>
      <div className="with-inspector">
        <div className="lab-main">
          <Section
            title="Execution schedule"
            subtitle="One assignment per transaction · 12 two-hour UTC slots"
            action={
              <button
                className={"button " + (compare ? "selected-button" : "")}
                onClick={() => setCompare(!compare)}
              >
                <GitCompareArrows size={16} />
                {compare ? "Close comparison" : "Compare schedules"}
              </button>
            }
          >
            {compare && (
              <div className="comparison-controls">
                <label>
                  Schedule A
                  <ArchiveSelector value={aName} onChange={setAName} />
                </label>
                <ArrowRight size={18} />
                <label>
                  Schedule B
                  <ArchiveSelector
                    value={bName}
                    onChange={setBName}
                    includeCurrent
                  />
                </label>
                <span className="caption">
                  A is archived · B{" "}
                  {bName === "current"
                    ? "uses workspace result"
                    : "is archived"}
                </span>
              </div>
            )}
            {(a.error || b.error) && compare && (
              <ErrorState error={(a.error || b.error) as Error} />
            )}
            {comparison.error && compare && (
              <ErrorState error={comparison.error} />
            )}
            {compare && comparison.isPending ? (
              <Loading text="Comparing complete TRAIN schedules…" />
            ) : (
              compare &&
              comparison.data && (
                <div
                  className="comparison-summary"
                  data-testid="comparison-summary"
                >
                  <Metric
                    label="Changed transactions"
                    value={comparison.data.changed_count}
                  />
                  <Metric
                    label="Δ Expected TRAIN cost (B − A)"
                    value={eth(comparison.data.delta_mean_eth)}
                    unit="ETH"
                  />
                  <Metric
                    label="Δ TRAIN CVaR (B − A)"
                    value={eth(comparison.data.delta_cvar_eth)}
                    unit="ETH"
                  />
                  <Metric
                    label="Δ Worst TRAIN cost (B − A)"
                    value={eth(comparison.data.delta_worst_eth)}
                    unit="ETH"
                  />
                </div>
              )
            )}
            <div className="toolbar">
              <select
                aria-label="Schedule priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="ALL">All priorities</option>
                {["URGENT", "STANDARD", "FLEXIBLE"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              {compare && (
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={onlyChanged}
                    onChange={(e) => setOnlyChanged(e.target.checked)}
                  />
                  Show changed transactions only
                </label>
              )}
              <span className="caption">
                Click a transaction to understand the decision ↗
              </span>
            </div>
            <ScheduleMatrix
              workload={workload}
              schedule={displayed.schedule}
              other={baseline?.schedule}
              onSelect={setSelected}
              changedOnly={compare && onlyChanged}
              priority={priority}
            />
          </Section>
          {compare && comparison.data && (
            <Section
              title="Changed decisions"
              subtitle="Mean price differences are transaction-level; CVaR is a joint schedule property."
            >
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Transaction</th>
                      <th>Gas</th>
                      <th>Window</th>
                      <th>A slot</th>
                      <th>B slot</th>
                      <th>Δ slots</th>
                      <th>A mean gwei</th>
                      <th>B mean gwei</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.data.changed.map((t) => (
                      <tr key={t.transaction_id}>
                        <td>
                          <button
                            className="table-link"
                            onClick={() => setSelected(t)}
                          >
                            {t.transaction_id}
                          </button>
                        </td>
                        <td>{num(t.gas_used)}</td>
                        <td>
                          {t.release_slot}–{t.deadline_slot}
                        </td>
                        <td>{t.slot_a}</td>
                        <td>{t.slot_b}</td>
                        <td>{t.slot_difference}</td>
                        <td>{price(t.mean_price_a)}</td>
                        <td>{price(t.mean_price_b)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <PathChart
                data={comparison.data.scenario_differences}
                xKey="date"
                series={[
                  {
                    key: "cost_a",
                    name: "Schedule A · TRAIN",
                    color: "#7d91b1",
                  },
                  {
                    key: "cost_b",
                    name: "Schedule B · TRAIN",
                    color: "#b8a6ef",
                  },
                ]}
              />
            </Section>
          )}
        </div>
        {selected && (
          <Inspector
            tx={selected}
            profile={profile}
            current={displayed.schedule}
            mean={mean.schedule}
            other={baseline?.schedule}
            onClose={() => setSelected(null)}
          />
        )}
      </div>
      <Section
        title="Solver diagnostics"
        subtitle="Optimal under the stated model. The objective includes the risk penalty."
      >
        <Diagnostics r={current} />
      </Section>
      <div className="next-action">
        <div>
          <h3>Inspect the risk behind this schedule</h3>
          <p>
            Explore TRAIN tail costs, or explicitly evaluate this frozen
            schedule on TEST.
          </p>
        </div>
        <div className="actions">
          <Link className="button" to="/risk">
            Explore CVaR <ArrowUpRight size={15} />
          </Link>
          <button
            className="button"
            disabled={evaluation.isPending}
            onClick={() => evaluation.mutate()}
          >
            Evaluate frozen schedule on TEST
          </button>
        </div>
      </div>
      {evaluation.isPending && <Loading />}
      {evaluation.error && <ErrorState error={evaluation.error} />}{" "}
      {evaluation.data && (
        <Section title="Frozen TEST evaluation">
          <TestBanner
            tail={evaluation.data.metrics.test_tail_scenario_count}
            exploratory={evaluation.data.exploratory || current.exploratory}
          />
          <div className="metrics four">
            <Metric
              label="TEST mean"
              value={eth(evaluation.data.metrics.test_mean_cost_eth)}
              unit="ETH"
            />
            <Metric
              label="TEST CVaR"
              value={eth(evaluation.data.metrics.test_cvar_eth)}
              unit="ETH"
            />
            <Metric
              label="Mean savings vs immediate"
              value={
                evaluation.data.metrics.test_savings_percent.toFixed(2) + "%"
              }
              positive
            />
            <Metric
              label="Worst TEST day"
              value={eth(evaluation.data.metrics.test_max_cost_eth)}
              unit="ETH"
            />
          </div>
        </Section>
      )}
    </>
  );
}

export function RiskPage() {
  const { current, meta } = useWorkspace();
  const sensitivity = useApi<Sensitivity[]>("study/sensitivity");
  const [hover, setHover] = useState<Sensitivity | null>(null);
  const groups = sensitivity.data
    ? Array.from(new Set(sensitivity.data.map((x) => x.schedule_id))).map(
        (id) => ({
          id,
          rows: sensitivity.data!.filter((x) => x.schedule_id === id),
        }),
      )
    : [];
  return (
    <>
      <PageHeader
        eyebrow="05 / TAIL RISK"
        title="Risk & CVaR"
        description="Understand the high-cost tail of the current schedule’s TRAIN distribution."
        action={<Origin r={current} />}
      />
      <div className="metrics four">
        <Metric label="Risk-aversion weight λ" value={current.lambda_risk} />
        <Metric
          label="Confidence α"
          value={(current.alpha * 100).toFixed(1) + "%"}
        />
        <Metric label="TRAIN VaR" value={eth(current.var_eth)} unit="ETH" />
        <Metric label="TRAIN CVaR" value={eth(current.cvar_eth)} unit="ETH" />
      </div>
      <Section
        title="Beyond the threshold"
        subtitle={`${meta.train_days} historical TRAIN scenarios · ${current.tail_scenario_count.toFixed(2)} tail equivalents`}
      >
        <CostDistribution
          points={current.scenario_costs}
          varEth={current.var_eth}
          cvarEth={current.cvar_eth}
        />
        <div className="two-col explanations">
          <div>
            <h3>VaR: the threshold</h3>
            <p>
              The lower empirical α-quantile. Costs strictly above this
              threshold occupy at most the upper 1 − α probability mass. VaR is
              not a tail average.
            </p>
            <MathBlock
              math={String.raw`\operatorname{VaR}_{\alpha}=\inf\{c:F(c)\geq\alpha\}`}
            />
          </div>
          <div>
            <h3>CVaR: the tail cost</h3>
            <p>
              CVaR includes fractional probability at the boundary. Hover an
              amber scenario to see Cₛ, η, ξₛ and qₛ.
            </p>
            <MathBlock math={String.raw`\xi_s=\max(C_s-\eta,0)`} />
            <MathBlock
              math={String.raw`\operatorname{CVaR}_{\alpha}=\eta+\frac{\sum_s q_s\xi_s}{1-\alpha}`}
            />
          </div>
        </div>
      </Section>
      <Section
        title="The TRAIN cost–risk trade-off"
        subtitle="Pre-specified λ grid · archived Phase 2 results at α = 0.95"
      >
        {sensitivity.error ? (
          <ErrorState error={sensitivity.error} />
        ) : sensitivity.data ? (
          <>
            <div className="frontier-chart">
              <ResponsiveContainer>
                <ScatterChart
                  margin={{ top: 20, right: 40, left: 40, bottom: 30 }}
                >
                  <CartesianGrid stroke="#272f3e" />
                  <XAxis
                    type="number"
                    dataKey="train_expected_cost_eth"
                    domain={["auto", "auto"]}
                    name="Expected TRAIN cost"
                    tickFormatter={(v) => Number(v).toFixed(5)}
                    label={{
                      value: "Expected TRAIN cost (ETH)",
                      position: "bottom",
                      offset: 10,
                      fill: "#a2aec2",
                    }}
                  />
                  <YAxis
                    type="number"
                    dataKey="train_cvar_eth"
                    domain={["auto", "auto"]}
                    name="TRAIN CVaR"
                    tickFormatter={(v) => Number(v).toFixed(4)}
                    label={{
                      value: "TRAIN CVaR95 (ETH)",
                      angle: -90,
                      position: "left",
                      offset: 20,
                      fill: "#a2aec2",
                    }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const r = payload[0].payload as Sensitivity;
                      return (
                        <div className="chart-tooltip">
                          <b>λ = {r.lambda_risk}</b>
                          <p>Mean: {eth(r.train_expected_cost_eth)} ETH</p>
                          <p>CVaR: {eth(r.train_cvar_eth)} ETH</p>
                          <p>Worst: {eth(r.train_worst_cost_eth)} ETH</p>
                          <p>Schedule {r.schedule_id}</p>
                        </div>
                      );
                    }}
                  />
                  <Scatter
                    data={sensitivity.data}
                    fill="#b9a7f0"
                    line={{ stroke: "#6c608e" }}
                    onClick={(p) => setHover(p.payload as Sensitivity)}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="regimes">
              {groups.map((g, i) => (
                <button key={g.id} onClick={() => setHover(g.rows[0])}>
                  <span>REGIME {i + 1}</span>
                  <b>λ {g.rows.map((r) => r.lambda_risk).join(" · ")}</b>
                  <code>{g.id}</code>
                </button>
              ))}
            </div>
            {hover && (
              <div className="explanation">
                Schedule {hover.schedule_id}: expected TRAIN cost{" "}
                {eth(hover.train_expected_cost_eth)} ETH; CVaR95{" "}
                {eth(hover.train_cvar_eth)} ETH.
              </div>
            )}
            <p className="caption">
              The decision response is piecewise constant because execution
              decisions are discrete. Identical schedule IDs identify the same
              assignment. The current workspace α may differ from this archived
              grid.
            </p>
          </>
        ) : (
          <Loading />
        )}
      </Section>
      <div className="next-action">
        <div>
          <h3>Expected cost + λ × CVaR</h3>
          <p>
            λ = 0 minimizes expected expenditure. Larger λ increases the
            importance of tail-risk reduction.
          </p>
        </div>
        <Link className="button" to="/optimizer">
          Adjust risk weight <ArrowRight size={16} />
        </Link>
      </div>
    </>
  );
}

type ScenarioView = {
  split: string;
  date: string;
  selected_cost_eth: number;
  immediate_cost_eth: number;
  mean_price_cost_eth: number;
  path: { slot: number; gas_price_gwei: number; utc_range: string }[];
};
export function ScenarioPage() {
  const { current, meta, markTest, workload } = useWorkspace();
  const [split, setSplit] = useState<"TRAIN" | "TEST">("TRAIN"),
    [day, setDay] = useState(""),
    [selector, setSelector] = useState("typical");
  const dates = useApi<HeatData>("data/heatmap?split=" + split);
  const scenario = useMutation({
    mutationFn: () =>
      api<ScenarioView>("analysis/scenario", {
        schedule: current.schedule,
        alpha: current.alpha,
        split,
        day: day || null,
        selector,
      }),
  });
  useEffect(() => {
    scenario.mutate();
  }, [split, day, selector, current.schedule_id]);
  return (
    <>
      <PageHeader
        eyebrow="06 / HISTORICAL TRAJECTORIES"
        title="Scenario explorer"
        description="Evaluate the same frozen schedule under one complete historical gas-price path."
        action={<Origin r={current} />}
      />
      <div className="toolbar">
        <div className="segmented">
          {(["TRAIN", "TEST"] as const).map((s) => (
            <button
              key={s}
              className={split === s ? "active" : ""}
              onClick={() => {
                setSplit(s);
                setDay("");
                if (s === "TEST") markTest();
              }}
            >
              {s}
            </button>
          ))}
        </div>
        {["typical", "high", "worst"].map((s) => (
          <button
            className={
              "button " + (!day && selector === s ? "selected-button" : "")
            }
            key={s}
            onClick={() => {
              setSelector(s);
              setDay("");
            }}
          >
            {s[0].toUpperCase() + s.slice(1)} {split} day
          </button>
        ))}
        <select
          aria-label="Historical scenario date"
          value={day}
          onChange={(e) => setDay(e.target.value)}
        >
          <option value="">Use selected preset</option>
          {dates.data?.dates.map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
      </div>
      {split === "TEST" && (
        <TestBanner
          tail={(1 - current.alpha) * meta.test_days}
          exploratory={current.exploratory}
        />
      )}{" "}
      {scenario.error ? (
        <ErrorState error={scenario.error} />
      ) : scenario.isPending || !scenario.data ? (
        <Loading />
      ) : (
        <>
          <Section
            title={scenario.data.date + " · " + split}
            subtitle={
              split === "TEST"
                ? "OUT-OF-SAMPLE TEST DAY · no model fitting occurs here"
                : "One whole historical TRAIN scenario. Typical/high/worst refer to costs under the current schedule."
            }
          >
            <PathChart
              data={scenario.data.path}
              xKey="slot"
              unit="gwei"
              series={[
                {
                  key: "gas_price_gwei",
                  name: "Observed median gas price",
                  color: "#b7a4ee",
                },
              ]}
              height={330}
            />
          </Section>
          <div className="metrics three">
            <Metric
              label={"Immediate · " + split}
              value={eth(scenario.data.immediate_cost_eth)}
              unit="ETH"
            />
            <Metric
              label={"Mean price · " + split}
              value={eth(scenario.data.mean_price_cost_eth)}
              unit="ETH"
            />
            <Metric
              label={"Current schedule · " + split}
              value={eth(scenario.data.selected_cost_eth)}
              unit="ETH"
            />
          </div>
          <Section
            title="Frozen assignments"
            subtitle="The selected historical day changes costs, never the schedule."
          >
            <div className="assignment-strip">
              {workload.map((t) => (
                <span key={t.transaction_id}>
                  {t.transaction_id.replace("treasury_", "TX-")}
                  <b>{current.schedule[t.transaction_id]}</b>
                </span>
              ))}
            </div>
          </Section>
        </>
      )}
    </>
  );
}

export function ResultsPage() {
  const { meta, current, markTest, viewedTest } = useWorkspace();
  const saved = useApi<MetricRow[]>("study/results"),
    sensitivity = useApi<Sensitivity[]>("study/sensitivity");
  const [distinct, setDistinct] = useState(true),
    [strategy, setStrategy] = useState("mean_price");
  const selected = useApi<Result>(
    "study/archive/" + strategy,
    strategy !== "current",
  );
  const result = strategy === "current" ? current : selected.data;
  const evaluation = useMutation({
    mutationFn: (r: Result) =>
      api<Evaluation>("evaluation/frozen-schedule", {
        schedule: r.schedule,
        alpha: r.alpha,
      }),
  });
  useEffect(() => {
    markTest();
  }, []);
  useEffect(() => {
    if (result) evaluation.mutate(result);
  }, [result]);
  let rows = saved.data ?? [];
  if (distinct) {
    const seen = new Set<string>();
    rows = rows.filter((r) => {
      const id =
        sensitivity.data?.find((s) => s.strategy === r.strategy)?.schedule_id ??
        (r.strategy === "mean_price"
          ? sensitivity.data?.find((s) => s.lambda_risk === 0)?.schedule_id
          : r.strategy);
      if (id && seen.has(id)) return false;
      if (id) seen.add(id);
      return true;
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="07 / HELD-OUT EVALUATION"
        title="Frozen schedule results"
        description="Schedules fitted on TRAIN, then evaluated on unseen TEST days. No TEST-day re-optimization."
      />
      <TestBanner
        tail={
          result ? (1 - result.alpha) * meta.test_days : meta.test_tail_count
        }
        exploratory={
          !!result?.exploratory
        }
      />
      <Section
        title="Out-of-sample descriptive comparison"
        subtitle="Validated Phase 2 archive · all monetary values in ETH"
        action={
          <div className="segmented">
            <button
              className={distinct ? "active" : ""}
              onClick={() => setDistinct(true)}
            >
              Distinct schedules
            </button>
            <button
              className={!distinct ? "active" : ""}
              onClick={() => setDistinct(false)}
            >
              All lambda values
            </button>
          </div>
        }
      >
        {saved.error ? (
          <ErrorState error={saved.error} />
        ) : !saved.data ? (
          <Loading />
        ) : (
          <div className="table-scroll">
            <table className="results-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Mean</th>
                  <th>Median</th>
                  <th>Std. dev.</th>
                  <th>VaR95</th>
                  <th>CVaR95</th>
                  <th>Worst</th>
                  <th>Best</th>
                  <th>Savings ETH</th>
                  <th>Savings %</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.strategy}
                    className={strategy === r.strategy ? "selected-row" : ""}
                  >
                    <td>
                      <button
                        className="table-link"
                        onClick={() => setStrategy(r.strategy)}
                      >
                        {label(r.strategy)}
                      </button>
                    </td>
                    {[
                      "mean_cost_eth",
                      "median_cost_eth",
                      "std_cost_eth",
                      "var_eth",
                      "cvar_eth",
                      "max_cost_eth",
                      "min_cost_eth",
                      "savings_eth",
                    ].map((k) => (
                      <td key={k}>{eth(r["test_" + k])}</td>
                    ))}
                    <td className="positive">
                      {Number(r.test_savings_percent).toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="caption">
          Savings = ratio of mean costs relative to immediate execution. No
          strategy is labelled “best lambda”; this table does not choose a risk
          weight.
        </p>
      </Section>
      <Section
        title="Daily costs & distribution"
        subtitle="The same selected frozen schedule evaluated across all TEST days"
        action={
          <ArchiveSelector
            value={strategy}
            onChange={setStrategy}
            includeCurrent
          />
        }
      >
        {selected.error && strategy !== "current" ? (
          <ErrorState error={selected.error} />
        ) : evaluation.error ? (
          <ErrorState error={evaluation.error} />
        ) : evaluation.isPending || !evaluation.data ? (
          <Loading />
        ) : (
          <>
            <div className="metrics four">
              <Metric
                label="Mean TEST cost"
                value={eth(evaluation.data.metrics.test_mean_cost_eth)}
                unit="ETH"
              />
              <Metric
                label="TEST CVaR"
                value={eth(evaluation.data.metrics.test_cvar_eth)}
                unit="ETH"
              />
              <Metric
                label="Mean savings"
                value={
                  evaluation.data.metrics.test_savings_percent.toFixed(2) + "%"
                }
                positive
              />
              <Metric
                label="Worst TEST cost"
                value={eth(evaluation.data.metrics.test_max_cost_eth)}
                unit="ETH"
              />
            </div>
            <h3>Chronological TEST daily costs</h3>
            <PathChart
              data={evaluation.data.daily_costs}
              xKey="test_day"
              series={[
                { key: "immediate", name: "Immediate", color: "#7891b5" },
                {
                  key: "selected",
                  name:
                    strategy === "current"
                      ? "Current frozen schedule"
                      : label(strategy),
                  color: "#b6a2ed",
                },
              ]}
              height={320}
            />
            <h3>Ordered TEST cost distribution</h3>
            <CostDistribution
              points={evaluation.data.sorted_costs}
              varEth={evaluation.data.metrics.test_var_eth}
              cvarEth={evaluation.data.metrics.test_cvar_eth}
            />
          </>
        )}
      </Section>
    </>
  );
}
