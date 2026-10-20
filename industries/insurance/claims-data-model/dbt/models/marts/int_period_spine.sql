{{ config(materialized='ephemeral') }}
-- Every calendar month from the first ledger period or payment month to the last.
with bounds as (
    select least(min(l.period_month), (select min(payment_period) from {{ ref('stg_claims__claim_payments') }})) as lo,
           greatest(max(l.period_month), (select max(payment_period) from {{ ref('stg_claims__claim_payments') }})) as hi
      from {{ ref('stg_commission__ledger') }} l
)
select to_char(m, 'YYYY-MM') as period_month
  from bounds,
       generate_series(to_date(lo, 'YYYY-MM'), to_date(hi, 'YYYY-MM'), interval '1 month') as m
