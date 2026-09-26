import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Database,
  Layers,
  FlaskConical,
  ShieldCheck,
  CalendarCheck,
  Search,
  Download,
} from "lucide-react";
import {
  BarChart,
  Bar,
  Cell,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from "recharts";
import { useWorkspace } from "../App";
import {
  useApi,
  type HeatData,
  type Tx,
  type Profile,
  num,
  price,
  range,
} from "../api";
import {
  PageHeader,
  Section,
  Metric,
  Loading,
  ErrorState,
  PathChart,
  Heatmap,
  Inspector,
  Priority,
  TestBanner,
  Badge,
  tooltipStyle,
} from "../components";

export function Overview() {
  const { meta, profile } = useWorkspace();
  const stages = [
    ["01", "Ethereum data", "Observed gas prices & gas use", Database],
    ["02", "Daily scenarios", "Complete historical trajectories", Layers],
    [
      "03",
      "Treasury workload",
      "Observed gas + timing assumptions",
      CalendarCheck,
    ],
    ["04", "MILP + CVaR", "One schedule, explicit tail risk", FlaskConical],
    ["05", "Frozen evaluation", "Unseen TEST days", ShieldCheck],
  ] as const;
  return (
    <>
      <PageHeader
        eyebrow="ETHEREUM MAINNET / QUANTITATIVE RESEARCH"
        title="GasOps"
        description="Stochastic Ethereum Transaction Scheduling"
        action={
          <Link className="button primary" to="/optimizer">
            Open optimization lab <ArrowUpRight size={17} />
          </Link>
        }
      />
      <div className="overview-intro">
        <h2>
          The cost of waiting.
          <br />
          <span>The value of controlling risk.</span>
        </h2>
        <p>
          Schedule delay-tolerant transactions under gas-price uncertainty.
          Explore how expected cost and extreme-cost exposure change when you
          choose when to execute.
        </p>
      </div>
      <div className="metrics four overview-metrics">
        <Metric
          label="Underlying Ethereum transactions"
          value={new Intl.NumberFormat("en", {
            notation: "compact",
            maximumFractionDigits: 1,
          }).format(Number(meta.quality.raw_transaction_observations))}
          detail={
            num(Number(meta.quality.raw_transaction_observations)) +
            " observed source rows"
          }
        />
        <Metric
          label="Historical TRAIN scenarios"
          value={meta.train_days}
          detail={`${meta.config.train_start} → ${meta.config.train_end}`}
        />
        <Metric
          label="Held-out TEST days"
          value={meta.test_days}
          detail={`${meta.config.test_start} → ${meta.config.test_end}`}
        />
        <Metric
          label="Treasury transactions"
          value={meta.transaction_count}
          detail={`${meta.slots} slots · ${meta.binary_decisions} binary decisions`}
        />
      </div>
      <div className="overview-grid">
        <Section
          title="The daily execution window"
          subtitle="Mean of TRAIN slot medians · gwei / gas"
          action={
            <Link className="text-link" to="/data">
              Explore data <ArrowUpRight size={14} />
            </Link>
          }
        >
          <PathChart
            data={profile}
            xKey="slot"
            series={[
              { key: "mean_gwei", name: "TRAIN mean price", color: "#a899ed" },
            ]}
            unit="gwei"
            height={260}
          />
        </Section>
        <div className="research-note">
          <span className="eyebrow">THE RESEARCH QUESTION</span>
          <h3>When should a treasury execute?</h3>
          <p>
            The lowest expected-cost schedule may expose the treasury to higher
            extreme costs. CVaR makes this trade-off measurable.
          </p>
          <div className="note-rule" />
          <dl>
            <dt>Price source</dt>
            <dd>Dune · gas.fees</dd>
            <dt>Decision model</dt>
            <dd>Static here-and-now</dd>
            <dt>Risk measure</dt>
            <dd>CVaR {(meta.alpha * 100).toFixed(0)}%</dd>
            <dt>Solver</dt>
            <dd>Pyomo / HiGHS</dd>
          </dl>
          <Link className="text-link" to="/model">
            Understand the mathematics <ArrowRight size={15} />
          </Link>
        </div>
      </div>
      <Section
        title="From observations to decisions"
        subtitle="A reproducible, offline pipeline"
      >
        <div className="pipeline">
          {stages.map(([n, title, sub, Icon]) => (
            <div key={n}>
              <div className="pipeline-top">
                <span>{n}</span>
                <Icon size={18} />
              </div>
              <h3>{title}</h3>
              <p>{sub}</p>
            </div>
          ))}
        </div>
      </Section>
      <div className="next-action">
        <div>
          <span className="eyebrow">START WITH A QUESTION</span>
          <h3>What changes when λ moves from 0 to 0.05?</h3>
          <p>
            Run both models, compare the schedules, then inspect a changed
            transaction.
          </p>
        </div>
        <Link className="button" to="/optimizer">
          Run the experiment <ArrowRight size={17} />
        </Link>
      </div>
    </>
  );
}

export function DataPage() {
  const { meta, workload, markTest } = useWorkspace();
  const [split, setSplit] = useState("TRAIN"),
    [day, setDay] = useState(meta.config.train_start);
  const history = useApi<
      {
        day: string;
        slot: number;
        slot_start_utc: string;
        median_gas_price_gwei: number;
      }[]
    >("data/gas-history?split=" + split),
    heat = useApi<HeatData>("data/heatmap"),
    gas = useApi<{
      sample_count: number;
      bins: { lower: number; upper: number; count: number }[];
      selected: Tx[];
    }>("data/gas-used");
  const { profile } = useWorkspace();
  return (
    <>
      <PageHeader
        eyebrow="01 / EMPIRICAL EVIDENCE"
        title="Data explorer"
        description="Real Ethereum observations, preserved as complete daily price trajectories."
        action={<Badge tone="green">Verified local archive</Badge>}
      />
      <div className="provenance-strip">
        <div>
          <span>Source</span>
          <b>Dune Analytics · gas.fees</b>
        </div>
        <div>
          <span>Network / timezone</span>
          <b>Ethereum Mainnet · UTC</b>
        </div>
        <div>
          <span>TRAIN</span>
          <b>
            {meta.config.train_start} → {meta.config.train_end}
          </b>
        </div>
        <div>
          <span>TEST</span>
          <b>
            {meta.config.test_start} → {meta.config.test_end}
          </b>
        </div>
      </div>
      <div className="assumptions">
        <div>
          <Badge>EMPIRICAL</Badge> Gas price · gas used · transaction hash
        </div>
        <div>
          <Badge tone="amber">BUSINESS ASSUMPTIONS</Badge> Release · deadline ·
          flexibility class
        </div>
      </div>
      <Section
        title="Gas prices through time"
        subtitle="Two-hour slot median · gwei / gas · execution-price proxy"
        action={
          <div className="segmented">
            {["TRAIN", "TEST", "ALL"].map((s) => (
              <button
                className={split === s ? "active" : ""}
                onClick={() => {
                  setSplit(s);
                  if (s !== "TRAIN") markTest();
                }}
                key={s}
              >
                {s === "ALL" ? "Full period" : s}
              </button>
            ))}
          </div>
        }
      >
        {split !== "TRAIN" && <TestBanner tail={meta.test_tail_count} />}{" "}
        {history.error ? (
          <ErrorState error={history.error} />
        ) : !history.data ? (
          <Loading />
        ) : (
          <PathChart
            data={history.data.map((x) => ({
              ...x,
              time: x.slot_start_utc.slice(0, 16).replace("T", " "),
            }))}
            xKey="time"
            unit="gwei"
            series={[
              {
                key: "median_gas_price_gwei",
                name: split + " slot median",
                color: "#a899ed",
              },
            ]}
            height={300}
          />
        )}
      </Section>
      <Section
        title="Which hours tend to cost less?"
        subtitle="Distribution across TRAIN days, using each day’s slot median"
      >
        <div className="chart">
          <ResponsiveContainer>
            <BarChart data={profile}>
              <CartesianGrid vertical={false} stroke="#272f3e" />
              <XAxis dataKey="slot" />
              <YAxis />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(v) => [price(Number(v)), "gwei / gas"]}
                labelFormatter={(v) => `Slot ${v} · ${range(Number(v))} UTC`}
              />
              <Legend />
              <Bar
                dataKey="mean_gwei"
                name="TRAIN mean"
                fill="#9d8cdb"
                radius={[3, 3, 0, 0]}
              />
              <Bar
                dataKey="median_gwei"
                name="TRAIN median"
                fill="#617493"
                radius={[3, 3, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Slot / UTC</th>
                <th>Mean</th>
                <th>Median</th>
                <th>p25</th>
                <th>p75</th>
              </tr>
            </thead>
            <tbody>
              {profile.map((p) => (
                <tr key={p.slot}>
                  <td>
                    {p.slot} · {p.utc_range}
                  </td>
                  <td>{price(p.mean_gwei)}</td>
                  <td>{price(p.median_gwei)}</td>
                  <td>{price(p.p25_gwei)}</td>
                  <td>{price(p.p75_gwei)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section
        title="One day. One scenario."
        subtitle="TRAIN trajectories · click a row to inspect it"
      >
        {heat.error ? (
          <ErrorState error={heat.error} />
        ) : heat.data ? (
          <>
            <Heatmap data={heat.data} selected={day} onSelect={setDay} />
            <PathChart
              data={heat.data.prices[heat.data.dates.indexOf(day)].map(
                (v, i) => ({ slot: i + 1, price: v }),
              )}
              xKey="slot"
              unit="gwei"
              series={[
                { key: "price", name: day + " · TRAIN", color: "#b8a6ef" },
              ]}
            />
          </>
        ) : (
          <Loading />
        )}
      </Section>
      <Section
        title="Observed gas requirements"
        subtitle="TRAIN candidate distribution; markers below show the actual selected observations"
      >
        {gas.error ? (
          <ErrorState error={gas.error} />
        ) : gas.data ? (
          <>
            <div className="chart">
              <ResponsiveContainer>
                <BarChart data={gas.data.bins}>
                  <CartesianGrid vertical={false} stroke="#272f3e" />
                  <XAxis
                    dataKey="lower"
                    tickFormatter={(v) => num(Math.round(v))}
                    minTickGap={65}
                  />
                  <YAxis />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(v) =>
                      `Gas bin starting at ${num(Math.round(Number(v)))}`
                    }
                  />
                  <Bar
                    dataKey="count"
                    name="Observed transactions"
                    fill="#8173b3"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="selected-gas">
              {workload.map((t) => (
                <span
                  key={t.transaction_id}
                  title={t.transaction_id + " · " + num(t.gas_used) + " gas"}
                >
                  {num(t.gas_used)}
                </span>
              ))}
            </div>
            <p className="caption">
              {num(gas.data.sample_count)} candidate observations →{" "}
              {workload.length} selected integers. No synthetic interpolation or
              winsorization. Selected after documented TRAIN bounds and
              trimming.
            </p>
          </>
        ) : (
          <Loading />
        )}
      </Section>
      <Section
        title="Extraction provenance"
        subtitle="Exact SQL and hashes remain in the archived metadata"
      >
        <div className="two-col">
          {Object.entries(meta.provenance).map(([name, p]) => (
            <div key={name} className="provenance-detail">
              <h3>{name}</h3>
              <dl>
                <dt>Execution ID</dt>
                <dd className="hash">{p.source_reference}</dd>
                <dt>Extracted UTC</dt>
                <dd>{p.extracted_at_utc}</dd>
                <dt>SQL SHA-256</dt>
                <dd className="hash">{p.sql_sha256}</dd>
                <dt>File SHA-256</dt>
                <dd className="hash">{p.sha256}</dd>
              </dl>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}

export function WorkloadPage() {
  const { workload, profile, mean, current } = useWorkspace();
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("ALL"),
    [sort, setSort] = useState("transaction_id"),
    [selected, setSelected] = useState<Tx | null>(null);
  const rows = workload
    .filter(
      (t) =>
        (filter === "ALL" || t.priority_class === filter) &&
        `${t.transaction_id} ${t.gas_used}`.includes(search),
    )
    .sort((a, b) =>
      sort === "gas_used"
        ? b.gas_used - a.gas_used
        : sort === "window_length"
          ? a.window_length - b.window_length
          : a.transaction_id.localeCompare(b.transaction_id),
    );
  return (
    <>
      <PageHeader
        eyebrow="02 / TREASURY INPUTS"
        title="Treasury workload"
        description="Observed gas requirements. Explicit timing assumptions. One fixed workload across every day."
      />
      <div className="metrics four">
        <Metric label="Transactions" value={workload.length} />
        {["URGENT", "STANDARD", "FLEXIBLE"].map((c) => (
          <Metric
            key={c}
            label={c.toLowerCase()}
            value={workload.filter((t) => t.priority_class === c).length}
            detail={`${workload.find((t) => t.priority_class === c)?.window_length} feasible two-hour slots`}
          />
        ))}
      </div>
      <div className="with-inspector">
        <Section
          title="Transaction register"
          subtitle="Select a transaction to inspect its feasible execution window"
        >
          <div className="toolbar">
            <label className="search">
              <Search size={16} />
              <input
                aria-label="Search transactions"
                placeholder="Search ID or gas…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <select
              aria-label="Priority filter"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="ALL">All priorities</option>
              {["URGENT", "STANDARD", "FLEXIBLE"].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
            <select
              aria-label="Sort transactions"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="transaction_id">Transaction ID</option>
              <option value="gas_used">Gas: high to low</option>
              <option value="window_length">Window: narrow first</option>
            </select>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Gas used</th>
                  <th>Release</th>
                  <th>Deadline</th>
                  <th>Window</th>
                  <th>Priority</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr
                    key={t.transaction_id}
                    className={
                      selected?.transaction_id === t.transaction_id
                        ? "selected-row"
                        : ""
                    }
                  >
                    <td>
                      <button
                        className="table-link"
                        onClick={() => setSelected(t)}
                      >
                        {t.transaction_id}
                      </button>
                    </td>
                    <td>{num(t.gas_used)}</td>
                    <td>{t.release_slot}</td>
                    <td>{t.deadline_slot}</td>
                    <td>{t.window_length} slots</td>
                    <td>
                      <Priority value={t.priority_class} />
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={"Inspect " + t.transaction_id}
                        onClick={() => setSelected(t)}
                      >
                        <ArrowUpRight size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && <p className="empty">No matching transactions.</p>}
          </div>
        </Section>
        {selected && (
          <Inspector
            tx={selected}
            profile={profile}
            current={current.schedule}
            mean={mean.schedule}
            onClose={() => setSelected(null)}
          />
        )}
      </div>
    </>
  );
}

export function Methodology() {
  const { meta } = useWorkspace();
  const steps = [
    [
      "Measure",
      "Dune gas.fees, Ethereum Mainnet. Raw wei converted explicitly to gwei and checked against execution fees.",
    ],
    [
      "Aggregate",
      "Approximate median gas prices in twelve two-hour UTC slots. Within-slot extremes are not preserved by the median.",
    ],
    [
      "Preserve trajectories",
      "A scenario is a complete daily price path. Slots are never sampled independently.",
    ],
    [
      "Separate chronologically",
      `${meta.train_days} TRAIN days precede ${meta.test_days} TEST days. No overlap; no look-ahead.`,
    ],
    [
      "Construct workload",
      "Day-stratified TRAIN sample; observed integer gas requirements. Releases, deadlines and priority windows are business assumptions.",
    ],
    [
      "Fit and freeze",
      "Mean-price or mean-plus-CVaR model solved by HiGHS on TRAIN. One common schedule is fixed before observing prices.",
    ],
    [
      "Evaluate",
      "Apply that frozen schedule to each TEST trajectory. No test-day re-optimization and no TEST-based lambda selection.",
    ],
  ];
  return (
    <>
      <PageHeader
        eyebrow="RESEARCH PROTOCOL"
        title="Methodology & limitations"
        description="What the experiment establishes, and where its assumptions stop."
      />
      <div className="method-flow">
        {steps.map(([t, d], i) => (
          <div key={t}>
            <span>{String(i + 1).padStart(2, "0")}</span>
            <div>
              <h2>{t}</h2>
              <p>{d}</p>
            </div>
          </div>
        ))}
      </div>
      <TestBanner tail={meta.test_tail_count} />
      <Section
        title="Interpretation boundaries"
        subtitle="An empirical decision-support experiment under stated assumptions"
      >
        <div className="limitations">
          {[
            [
              "Price proxy",
              "Two-hour median execution prices are not guaranteed attainable fees. Blob resource charges are excluded.",
            ],
            [
              "Static decisions",
              "One here-and-now schedule. No dynamic recourse, gas-price prediction, bidding or mempool simulation.",
            ],
            [
              "Execution assumptions",
              "Gas requirements are fixed. Nonce dependencies, inclusion uncertainty and smart-contract behavior are outside the model.",
            ],
            [
              "Scope",
              "No MEV, Layer 2 routing, batching, wallet connection or transaction execution.",
            ],
            [
              "Generalization",
              "Temporal dependence and regime changes can affect results. No guarantee of future savings.",
            ],
            [
              "Tail precision",
              `TEST CVaR95 uses ${meta.test_tail_count.toFixed(2)} scenario equivalents; no statistical-significance claim.`,
            ],
          ].map(([t, d]) => (
            <div key={t}>
              <h3>{t}</h3>
              <p>{d}</p>
            </div>
          ))}
        </div>
      </Section>
      <Section title="Reproducibility">
        <dl>
          <dt>Dataset identity</dt>
          <dd className="hash">{meta.dataset_id}</dd>
          <dt>Source</dt>
          <dd>{meta.source}</dd>
          <dt>Missing TRAIN / TEST days</dt>
          <dd>
            {(meta.quality.train_dropped_or_absent_days as string[]).length} /{" "}
            {(meta.quality.test_dropped_or_absent_days as string[]).length}
          </dd>
          <dt>Interpolation</dt>
          <dd>None</dd>
          <dt>Runtime network</dt>
          <dd>None required after installation. No Dune API key required.</dd>
          <dt>Core</dt>
          <dd>Validated gasopt Python package · Pyomo / HiGHS</dd>
        </dl>
        <p className="caption">
          API lifecycle follows{" "}
          <a
            href="https://fastapi.tiangolo.com/advanced/events/"
            target="_blank"
            rel="noreferrer"
          >
            FastAPI lifespan guidance
          </a>
          ; frontend tooling follows the{" "}
          <a href="https://vite.dev/guide/" target="_blank" rel="noreferrer">
            Vite guide
          </a>
          . External references are optional and do not participate in the
          offline application.
        </p>
      </Section>
    </>
  );
}
