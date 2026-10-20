select ledger_id,
       policy_id,
       agent_id,
       period_month::text as period_month,
       rate_id,
       split_pct,
       base_premium,
       commission_amt
  from {{ source('commission', 'commission_ledger') }}
