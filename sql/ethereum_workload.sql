-- TRAIN ONLY. Retain actual observed transaction hashes, gas use and fees.
-- First use a deterministic 1/4096 hash-prefix subsample (no gas-value ranking),
-- then take up to sample_per_day rows in seeded hash order per UTC day.
-- This is a day-stratified sample, not a frequency-weighted chain-wide sample.
WITH candidates AS (
    SELECT block_date, block_time, tx_hash, gas_used,
           CAST(gas_price AS DOUBLE) AS gas_price_raw,
           CAST(gas_price AS DOUBLE) * {{raw_to_gwei}} AS gas_price_gwei,
           tx_fee, tx_fee_usd,
           tx_fee - coalesce(element_at(tx_fee_breakdown, 'blob_fee'), 0) AS execution_fee_eth
    FROM gas.fees
    WHERE blockchain = 'ethereum'
      AND block_month >= date_trunc('month', DATE '{{train_start}}')
      AND block_date BETWEEN DATE '{{train_start}}' AND DATE '{{train_end}}'
      AND block_time >= TIMESTAMP '{{train_start}} 00:00:00'
      AND block_time < TIMESTAMP '{{train_end_exclusive}} 00:00:00'
      AND gas_used BETWEEN {{gas_used_min}} AND {{gas_used_max}}
      AND gas_price > 0
      AND substr(to_hex(tx_hash), 1, 3) = '000'
), ranked AS (
    SELECT *, row_number() OVER (
        PARTITION BY block_date
        ORDER BY to_hex(sha256(concat(tx_hash, to_utf8('{{sample_seed}}')))), tx_hash
    ) AS sample_rank
    FROM candidates
)
SELECT CAST(block_date AS VARCHAR) AS day,
       to_iso8601(block_time) AS block_time_utc,
       concat('0x', lower(to_hex(tx_hash))) AS tx_hash,
       gas_used, gas_price_raw, gas_price_gwei, tx_fee AS tx_fee_eth, tx_fee_usd,
       execution_fee_eth, sample_rank
FROM ranked
WHERE sample_rank <= {{sample_per_day}}
ORDER BY day, sample_rank, tx_hash
