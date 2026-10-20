{{ config(materialized='ephemeral') }}
-- Every calendar month from the first ledger period, payment month or loss month to the last.
with months as (
    select period_month from {{ ref('stg_commission__ledger') }}
    union all
    select payment_period from {{ ref('stg_claims__claim_payments') }}
    union all
    select loss_period from {{ ref('stg_claims__claims') }}
),
bounds as (
    select min(period_month) as lo, max(period_month) as hi from months
)
select to_char(m, 'YYYY-MM') as period_month
  from bounds,
       generate_series(to_date(lo, 'YYYY-MM'), to_date(hi, 'YYYY-MM'), interval '1 month') as m
