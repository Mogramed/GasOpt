-- DuneSQL. Render with python -m gasopt.data.dune render --config ...
-- Inclusive fixed UTC dates. Approximate quantiles use Dune's approx_percentile.
-- Preserve full trajectories; no random or independent slot sampling.
-- gas_price raw units MUST pass the fee-identity audit before use.
WITH source AS (
    SELECT block_date,
           date_trunc('day', block_time) + INTERVAL '2' HOUR *
               CAST(floor(hour(block_time) / 2.0) AS BIGINT) AS slot_start,
           CAST(floor(hour(block_time) / 2.0) AS INTEGER) + 1 AS slot,
           CAST(gas_price AS DOUBLE) AS gas_price_raw,
           CAST(gas_price AS DOUBLE) * 1e-9 AS gas_price_gwei,
           gas_used, tx_fee, tx_fee_usd,
           tx_fee - coalesce(element_at(tx_fee_breakdown, 'blob_fee'), 0) AS execution_fee_eth
    FROM gas.fees
    WHERE blockchain = 'ethereum'
      AND block_month >= date_trunc('month', DATE '2025-01-01')
      AND block_date BETWEEN DATE '2025-01-01' AND DATE '2026-03-31'
      AND block_time >= TIMESTAMP '2025-01-01 00:00:00'
      AND block_time < TIMESTAMP '2026-04-01 00:00:00'
), checked AS (
    SELECT *, gas_price_gwei > 0 AND gas_used > 0 AS valid,
        CASE WHEN gas_price_gwei > 0 AND gas_used > 0 AND execution_fee_eth > 0
             THEN abs(gas_price_gwei * gas_used * 1e-9 / execution_fee_eth - 1)
        END AS unit_relative_error
    FROM source
)
SELECT CAST(block_date AS VARCHAR) AS day,
       to_iso8601(slot_start) AS slot_start_utc,
       slot, count(*) AS transaction_count,
       count_if(valid) AS valid_transaction_count,
       approx_percentile(gas_price_gwei, 0.50) FILTER (WHERE valid) AS median_gas_price_gwei,
       avg(gas_price_gwei) FILTER (WHERE valid) AS mean_gas_price_gwei,
       approx_percentile(gas_price_gwei, 0.25) FILTER (WHERE valid) AS p25_gas_price_gwei,
       approx_percentile(gas_price_gwei, 0.75) FILTER (WHERE valid) AS p75_gas_price_gwei,
       approx_percentile(gas_price_gwei, 0.95) FILTER (WHERE valid) AS p95_gas_price_gwei,
       approx_percentile(gas_used, 0.50) FILTER (WHERE valid) AS median_gas_used,
       approx_percentile(gas_price_raw, 0.50) FILTER (WHERE valid) AS median_gas_price_raw,
       avg(tx_fee) FILTER (WHERE valid) AS mean_tx_fee_eth,
       avg(tx_fee_usd) FILTER (WHERE valid) AS mean_tx_fee_usd,
       count(unit_relative_error) AS unit_check_count,
       approx_percentile(unit_relative_error, 0.50) AS unit_check_median_relative_error,
       approx_percentile(unit_relative_error, 0.95) AS unit_check_p95_relative_error
FROM checked
GROUP BY block_date, slot_start, slot
ORDER BY day, slot
