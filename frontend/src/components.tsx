import { useMemo, useState, type ReactNode } from "react";
import katex from "katex";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  LoaderCircle,
  X,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
  LineChart,
  Line,
  Legend,
} from "recharts";
import {
  eth,
  num,
  price,
  range,
  type Tx,
  type Result,
  type Schedule,
  type Profile,
  type CostPoint,
  type HeatData,
} from "./api";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
export function Section({
  title,
  subtitle,
  children,
  action,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={"section " + className}>
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Metric({
  label,
  value,
  unit,
  detail,
  positive = false,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  detail?: string;
  positive?: boolean;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={positive ? "positive" : ""}>
        {value}
        <small>{unit}</small>
      </strong>
      {detail && <p>{detail}</p>}
    </div>
  );
}
export function Loading({ text = "Loading local study…" }: { text?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} />
      {text}
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="error">
      <AlertTriangle size={20} />
      <div>
        <strong>Unable to complete this request</strong>
        <p>{error.message}</p>
        {retry && <button onClick={retry}>Try again</button>}
      </div>
    </div>
  );
}
export function TestBanner({
  tail,
  exploratory = false,
}: {
  tail: number;
  exploratory?: boolean;
}) {
  return (
    <div className="notice" role="note">
      <AlertTriangle size={18} />
      <div>
        <strong>OUT-OF-SAMPLE · EVALUATION ONLY</strong>
        <p>
          TEST data did not influence model fitting or the pre-specified lambda
          grid. CVaR tail: {tail.toFixed(2)} scenario equivalents
          {tail < 10 ? " — thin tail; rankings may be unstable." : "."}
        </p>
        {exploratory && (
          <p>
            <b>
              Exploratory what-if — outside the pre-specified empirical study.
              Do not use TEST to choose lambda.
            </b>
          </p>
        )}
      </div>
    </div>
  );
}
export function MathBlock({ math }: { math: string }) {
  const html = useMemo(
    () =>
      katex.renderToString(math, { throwOnError: false, displayMode: true }),
    [math],
  );
  return <div className="math" dangerouslySetInnerHTML={{ __html: html }} />;
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Priority({ value }: { value: string }) {
  return (
    <span className={"priority " + value.toLowerCase()}>
      <i />
      {value.toLowerCase()}
    </span>
  );
}
export function Timeline({
  tx,
  selected,
  onSelect,
}: {
  tx: Tx;
  selected?: number;
  onSelect?: (n: number) => void;
}) {
  return (
    <div className="timeline">
      {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
        <button
          key={n}
          disabled={n < tx.release_slot || n > tx.deadline_slot}
          className={selected === n ? "selected" : ""}
          onClick={() => onSelect?.(n)}
          title={range(n) + " UTC"}
          aria-label={`Slot ${n}${selected === n ? ", assigned" : ""}`}
        >
          {selected === n ? <Check size={14} /> : n}
        </button>
      ))}
    </div>
  );
}
export function ScheduleMatrix({
  workload,
  schedule,
  other,
  onSelect,
  changedOnly = false,
  priority = "ALL",
}: {
  workload: Tx[];
  schedule: Schedule;
  other?: Schedule;
  onSelect: (tx: Tx) => void;
  changedOnly?: boolean;
  priority?: string;
}) {
  const rows = workload.filter(
    (t) =>
      (priority === "ALL" || t.priority_class === priority) &&
      (!changedOnly ||
        other?.[t.transaction_id] !== schedule[t.transaction_id]),
  );
  return (
    <div className="matrix-wrap">
      <table className="schedule-matrix" aria-label="Optimal schedule">
        <thead>
          <tr>
            <th>TRANSACTION / GAS</th>
            {Array.from({ length: 12 }, (_, i) => (
              <th key={i} title={range(i + 1) + " UTC"}>
                {String(i + 1).padStart(2, "0")}
                <small>{String(i * 2).padStart(2, "0")}:00</small>
              </th>
            ))}
            <th>CLASS</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((tx) => (
            <tr
              key={tx.transaction_id}
              className={
                other &&
                other[tx.transaction_id] !== schedule[tx.transaction_id]
                  ? "changed-row"
                  : ""
              }
            >
              <th>
                <button onClick={() => onSelect(tx)}>
                  {tx.transaction_id.replace("treasury_", "TX-")}
                  <small>{num(tx.gas_used)} gas</small>
                </button>
              </th>
              {Array.from({ length: 12 }, (_, i) => {
                const n = i + 1,
                  feasible = n >= tx.release_slot && n <= tx.deadline_slot,
                  active = schedule[tx.transaction_id] === n,
                  old =
                    other?.[tx.transaction_id] === n &&
                    other[tx.transaction_id] !== schedule[tx.transaction_id];
                return (
                  <td key={n}>
                    <button
                      className={
                        "slot-cell " +
                        (active
                          ? "assigned"
                          : old
                            ? "previous"
                            : feasible
                              ? "feasible"
                              : "unavailable")
                      }
                      onClick={() => onSelect(tx)}
                      aria-label={`${tx.transaction_id} slot ${n} ${active ? "assigned" : old ? "previous" : feasible ? "feasible" : "unavailable"}`}
                      title={`${tx.transaction_id} · ${range(n)} UTC · ${active ? "Current assignment" : old ? "Comparison assignment" : feasible ? "Feasible" : "Unavailable"}`}
                    >
                      {active ? (
                        <Check size={12} />
                      ) : old ? (
                        "○"
                      ) : feasible ? (
                        "·"
                      ) : (
                        "—"
                      )}
                    </button>
                  </td>
                );
              })}
              <td>
                <Priority value={tx.priority_class} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <p className="empty">No transactions match these filters.</p>
      )}
      <div className="matrix-legend">
        <span>✓ Current assignment</span>
        <span>○ Comparison assignment</span>
        <span>· Feasible window</span>
        <span>— Unavailable</span>
      </div>
    </div>
  );
}
export function Inspector({
  tx,
  profile,
  current,
  mean,
  other,
  onClose,
}: {
  tx: Tx;
  profile: Profile[];
  current?: Schedule;
  mean?: Schedule;
  other?: Schedule;
  onClose: () => void;
}) {
  return (
    <motion.aside
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="inspector"
      aria-label="Transaction inspector"
    >
      <div className="section-heading">
        <span className="eyebrow">DECISION INSPECTOR</span>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close inspector"
        >
          <X size={18} />
        </button>
      </div>
      <h2>{tx.transaction_id.replace("treasury_", "TX-")}</h2>
      <Priority value={tx.priority_class} />
      <div className="inspector-metrics">
        <Metric label="Observed gas" value={num(tx.gas_used)} />
        <Metric
          label="Feasible window"
          value={`${tx.release_slot} → ${tx.deadline_slot}`}
          detail={`${tx.window_length} slots · business assumption`}
        />
      </div>
      <Timeline tx={tx} selected={current?.[tx.transaction_id]} />
      <p>Must execute exactly once within this feasible window.</p>
      <dl>
        <dt>Immediate slot</dt>
        <dd>{tx.release_slot}</dd>
        <dt>Mean-price slot</dt>
        <dd>{mean?.[tx.transaction_id] ?? "—"}</dd>
        <dt>Comparison slot</dt>
        <dd>{other?.[tx.transaction_id] ?? "—"}</dd>
        <dt>Current slot</dt>
        <dd>{current?.[tx.transaction_id] ?? "—"}</dd>
      </dl>
      <h3>Admissible TRAIN mean prices</h3>
      <div className="price-list">
        {profile
          .filter((p) => tx.allowed_slots.includes(p.slot))
          .map((p) => (
            <div
              key={p.slot}
              className={
                current?.[tx.transaction_id] === p.slot ? "active" : ""
              }
            >
              <span>
                Slot {p.slot} <small>{range(p.slot)}</small>
              </span>
              <b>
                {price(p.mean_gwei)} <small>gwei</small>
              </b>
            </div>
          ))}
      </div>
      <div className="explanation">
        The mean-price model chooses the cheapest admissible mean-price slot.
        CVaR optimizes the <b>joint schedule</b>; a transaction’s contribution
        cannot be interpreted as an independent CVaR reduction.
      </div>
      <details>
        <summary>Observed transaction provenance</summary>
        <p className="hash">{tx.source_tx_hash}</p>
        <p>{tx.source_block_time_utc}</p>
      </details>
    </motion.aside>
  );
}
export const tooltipStyle = {
  backgroundColor: "#1c2330",
  border: "1px solid #394153",
  borderRadius: 8,
  color: "#edf0f7",
  fontSize: 12,
};
export function PathChart({
  data,
  xKey,
  series,
  unit = "ETH",
  height = 270,
}: {
  data: object[];
  xKey: string;
  series: { key: string; name: string; color: string }[];
  unit?: string;
  height?: number;
}) {
  return (
    <div style={{ height, width: "100%" }}>
      <ResponsiveContainer>
        <LineChart
          data={data}
          margin={{ left: 6, right: 20, top: 12, bottom: 5 }}
        >
          <CartesianGrid stroke="#272f3e" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: "#95a0b5", fontSize: 11 }}
            minTickGap={45}
          />
          <YAxis
            tick={{ fill: "#95a0b5", fontSize: 11 }}
            width={75}
            tickFormatter={(v) =>
              unit === "ETH" ? Number(v).toFixed(4) : Number(v).toFixed(2)
            }
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v, name) => [
              `${unit === "ETH" ? eth(Number(v)) : price(Number(v))} ${unit}`,
              name,
            ]}
          />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={1.8}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
export function CostDistribution({
  points,
  varEth,
  cvarEth,
}: {
  points: CostPoint[];
  varEth: number;
  cvarEth: number;
}) {
  return (
    <>
      <div className="chart-title">
        <span>Ordered historical scenario costs · ETH</span>
        <span>
          Amber = upper probability tail (fractional boundary included)
        </span>
      </div>
      <div className="risk-chart">
        <ResponsiveContainer>
          <BarChart
            data={points}
            margin={{ top: 20, left: 10, right: 24, bottom: 0 }}
          >
            <CartesianGrid stroke="#272f3e" vertical={false} />
            <XAxis
              dataKey="rank"
              tick={{ fill: "#95a0b5", fontSize: 11 }}
              minTickGap={35}
            />
            <YAxis
              width={70}
              tick={{ fill: "#95a0b5", fontSize: 11 }}
              tickFormatter={(v) => Number(v).toFixed(3)}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const p = payload[0].payload as CostPoint;
                return (
                  <div className="chart-tooltip">
                    <b>{p.date}</b>
                    <p>Cₛ: {eth(p.cost_eth)} ETH</p>
                    <p>η: {eth(p.eta_eth)} ETH</p>
                    <p>ξₛ: {eth(p.xi_eth)} ETH</p>
                    <p>qₛ: {p.probability.toFixed(6)}</p>
                    <p>Tail mass: {p.tail_mass.toFixed(6)}</p>
                  </div>
                );
              }}
            />
            <ReferenceLine
              y={varEth}
              stroke="#d4d9e5"
              strokeDasharray="4 4"
              label={{
                value: "VaR",
                fill: "#d4d9e5",
                position: "insideTopLeft",
              }}
            />
            <ReferenceLine
              y={cvarEth}
              stroke="#dfb776"
              strokeDasharray="3 3"
              label={{
                value: "CVaR",
                fill: "#dfb776",
                position: "insideTopLeft",
              }}
            />
            <Bar dataKey="cost_eth" isAnimationActive={false}>
              {points.map((p) => (
                <Cell
                  key={p.date}
                  fill={p.tail_mass > 0 ? "#dfb776" : "#8d80cf"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}
export function Heatmap({
  data,
  selected,
  onSelect,
}: {
  data: HeatData;
  selected: string;
  onSelect: (date: string) => void;
}) {
  const [hover, setHover] = useState<{
    day: string;
    slot: number;
    value: number;
  } | null>(null);
  const max = Math.max(...data.prices.flat());
  return (
    <>
      <div className="heat-controls">
        <label>
          Historical {data.split} day{" "}
          <select
            aria-label="Heatmap day"
            value={selected}
            onChange={(e) => onSelect(e.target.value)}
          >
            {data.dates.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
        <span>
          {hover
            ? `${hover.day} · slot ${hover.slot} · ${range(hover.slot)} UTC · ${price(hover.value)} gwei/gas`
            : "Hover a cell · click a full daily trajectory"}
        </span>
      </div>
      <div className="heatmap">
        <div className="heat-axis">
          {data.slots.map((s) => (
            <span key={s.slot}>
              {s.slot}
              <small>{range(s.slot)}</small>
            </span>
          ))}
        </div>
        <svg
          viewBox={`0 0 1200 ${data.dates.length * 2}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="Daily gas-price heatmap; use the day selector for keyboard interaction"
        >
          {data.prices.map((row, r) => (
            <g key={data.dates[r]} onClick={() => onSelect(data.dates[r])}>
              {row.map((v, c) => (
                <rect
                  key={c}
                  x={c * 100}
                  y={r * 2}
                  width={99}
                  height={2}
                  fill={`hsl(253 30% ${12 + (65 * Math.log1p(v)) / Math.log1p(max)}%)`}
                  onMouseEnter={() =>
                    setHover({ day: data.dates[r], slot: c + 1, value: v })
                  }
                >
                  <title>
                    {data.dates[r]} · {range(c + 1)} UTC · {price(v)} gwei/gas
                  </title>
                </rect>
              ))}
              {selected === data.dates[r] && (
                <rect
                  x={0}
                  y={r * 2}
                  width={1200}
                  height={2}
                  fill="none"
                  stroke="#f0d09b"
                  strokeWidth={2}
                />
              )}
            </g>
          ))}
        </svg>
        <div className="chart-title">
          <span>
            {data.dates[0]} → {data.dates.at(-1)}
          </span>
          <span>Log color scale · 0 → {price(max)} gwei/gas</span>
        </div>
      </div>
      <div className="explanation">
        <b>{selected}</b> — this entire row is one historical stochastic
        scenario. The 12 prices remain together.
      </div>
    </>
  );
}
export function Diagnostics({ r }: { r: Result }) {
  return (
    <>
      <div className="diagnostic-grid">
        {[
          ["Status", r.solver_status],
          ["Objective", eth(r.objective_value_eth) + " ETH"],
          ["Bound", eth(r.objective_bound_eth) + " ETH"],
          [
            "Relative gap",
            r.optimality_gap == null ? "—" : r.optimality_gap.toExponential(2),
          ],
          ["Variables", r.num_variables],
          ["Binary variables", r.num_binary_variables],
          ["Constraints", r.num_constraints],
          [
            "Solve time",
            r.solve_seconds == null
              ? "Archived"
              : r.solve_seconds.toFixed(3) + " s",
          ],
        ].map(([k, v]) => (
          <div key={k}>
            <span>{k}</span>
            <b>{v}</b>
          </div>
        ))}
      </div>
      <p className="caption">
        Before presolve. Branch-and-bound node count is not exposed by the
        current APPSI solver interface.
      </p>
    </>
  );
}
export function ResultMetrics({ r }: { r: Result }) {
  return (
    <div className="metrics four">
      <Metric
        label="Expected TRAIN cost"
        value={eth(r.expected_cost_eth)}
        unit="ETH"
      />
      <Metric
        label={`TRAIN CVaR ${(r.alpha * 100).toFixed(1)}%`}
        value={eth(r.cvar_eth)}
        unit="ETH"
      />
      <Metric label="TRAIN VaR" value={eth(r.var_eth)} unit="ETH" />
      <Metric
        label="Worst TRAIN scenario"
        value={eth(r.worst_case_cost_eth)}
        unit="ETH"
      />
    </div>
  );
}
