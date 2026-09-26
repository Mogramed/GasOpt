import { useQuery } from "@tanstack/react-query";
export type Schedule = Record<string, number>;
export type Tx = {
  transaction_id: string;
  gas_used: number;
  release_slot: number;
  deadline_slot: number;
  priority_class: string;
  window_length: number;
  allowed_slots: number[];
  source_tx_hash: string;
  source_block_time_utc: string;
};
export type CostPoint = {
  date: string;
  cost_eth: number;
  eta_eth: number;
  xi_eth: number;
  probability: number;
  rank: number;
  cumulative_probability: number;
  tail_mass: number;
};
export type Result = {
  origin: "live" | "cached_live" | "archived";
  dataset_id: string;
  strategy: string;
  schedule_id: string;
  lambda_risk: number;
  alpha: number;
  exploratory: boolean;
  schedule: Schedule;
  expected_cost_eth: number;
  var_eth: number;
  cvar_eth: number;
  worst_case_cost_eth: number;
  objective_value_eth: number;
  solver_status: string;
  objective_bound_eth: number | null;
  optimality_gap: number | null;
  num_variables: number;
  num_binary_variables: number;
  num_constraints: number;
  tail_scenario_count: number;
  node_count: number | null;
  scenario_costs: CostPoint[];
  changed_vs_mean_price: number;
  solve_seconds: number | null;
};
export type Profile = {
  slot: number;
  utc_range: string;
  mean_gwei: number;
  median_gwei: number;
  p25_gwei: number;
  p75_gwei: number;
};
export type Meta = {
  product: string;
  dataset_id: string;
  config: {
    train_start: string;
    train_end: string;
    test_start: string;
    test_end: string;
    lambda_grid: number[];
    min_train_tail_count: number;
  };
  quality: Record<string, number | string | string[]>;
  source: string;
  provenance: Record<
    string,
    {
      source_reference: string;
      extracted_at_utc: string;
      sql_sha256: string;
      sha256: string;
    }
  >;
  construction: Record<string, unknown>;
  train_days: number;
  test_days: number;
  transaction_count: number;
  slots: number;
  binary_decisions: number;
  alpha: number;
  train_tail_count: number;
  test_tail_count: number;
};
export type MetricRow = Record<string, number> & { strategy: string };
export type Sensitivity = {
  strategy: string;
  lambda_risk: number;
  train_expected_cost_eth: number;
  train_cvar_eth: number;
  train_worst_cost_eth: number;
  schedule_id: string;
};
export type Evaluation = {
  context: string;
  alpha: number;
  exploratory: boolean;
  schedule: Schedule;
  metrics: Record<string, number>;
  daily_costs: { test_day: string; immediate: number; selected: number }[];
  sorted_costs: CostPoint[];
  warning: string;
};
export type Compare = {
  changed: (Tx & {
    slot_a: number;
    slot_b: number;
    slot_difference: number;
    mean_price_a: number;
    mean_price_b: number;
  })[];
  changed_count: number;
  delta_mean_eth: number;
  delta_cvar_eth: number;
  delta_worst_eth: number;
  scenario_differences: {
    date: string;
    cost_a: number;
    cost_b: number;
    difference_eth: number;
  }[];
};
export type HeatData = {
  split: string;
  dates: string[];
  slots: { slot: number; utc_range: string }[];
  prices: number[][];
  unit: string;
};
export async function api<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api/v1/" + path, {
      method: body === undefined ? "GET" : "POST",
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error(
      "API unavailable. Check that the GasOps backend or Docker services are running.",
    );
  }
  if (!response.ok) {
    let d;
    try {
      d = await response.json();
    } catch {
      throw new Error(
        `API unavailable (${response.status}). Check the backend service.`,
      );
    }
    throw new Error(
      typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail),
    );
  }
  return response.json();
}
export function useApi<T>(path: string, enabled = true) {
  return useQuery<T>({
    queryKey: [path],
    queryFn: () => api<T>(path),
    enabled,
    staleTime: Infinity,
    retry: 1,
  });
}
export const eth = (n: number | null | undefined) =>
  n == null ? "—" : n.toFixed(9);
export const num = (n: number) => n.toLocaleString("en-US");
export const price = (n: number) => n.toFixed(n < 1 ? 4 : 3);
export const label = (s: string) =>
  s === "immediate"
    ? "Immediate"
    : s === "mean_price"
      ? "Mean price"
      : s === "expected_value_equivalence"
        ? "Expected-value equivalence"
        : s.startsWith("live_")
          ? `Live λ = ${s.replace("live_lambda_", "")}`
          : `CVaR λ = ${s.replace("cvar_lambda_", "")}`;
export const range = (n: number) =>
  `${String((n - 1) * 2).padStart(2, "0")}:00–${String(n * 2).padStart(2, "0")}:00`;
