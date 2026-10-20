-- Paid loss ratio per line of business per calendar month, with the commission paid next to it.
-- product        = line_of_business: the claims hub policies carry no product code, only LOBCd.
-- earned_premium = round(annual_premium / 12, 2) per in-force Commission Pay policy per month from its
--                  issue month (Postgres round on numeric is half away from zero, the same as Oracle ROUND;
--                  annual_premium / 12 is the base COMMISSION_PKG uses).
-- paid_loss      = claim_payments.net_amount by value-date month, attributed through the claim's policy.
-- loss_ratio     = paid_loss / earned_premium, 4 decimals, half away from zero; null without premium.
with spine as (
    select period_month from {{ ref('int_period_spine') }}
),
lines as (
    select line_of_business from {{ ref('stg_commission__products') }}
    union
    select line_of_business from {{ ref('stg_claims__policies') }}
),
earned as (
    select p.line_of_business, s.period_month,
           count(*) as policies_earning,
           sum(round(p.annual_premium / 12, 2)) as earned_premium
      from {{ ref('stg_commission__policies') }} p
      join spine s on s.period_month >= to_char(p.issued_date, 'YYYY-MM')
     where p.status = 'IN_FORCE'
     group by p.line_of_business, s.period_month
),
paid as (
    select c.line_of_business, pay.payment_period as period_month,
           count(*)                  as payments,
           sum(pay.indemnity_amount) as paid_indemnity,
           sum(pay.expense_amount)   as paid_expense,
           sum(pay.salvage_credit)   as salvage_recovered,
           sum(pay.net_amount)       as paid_loss
      from {{ ref('stg_claims__claim_payments') }} pay
      join {{ ref('stg_claims__claims') }} c using (claim_number)
     group by c.line_of_business, pay.payment_period
),
reported as (
    select line_of_business, loss_period as period_month,
           count(*) as claims_reported,
           sum(reserve_estimate) as reserve_reported
      from {{ ref('stg_claims__claims') }}
     group by line_of_business, loss_period
),
commission as (
    select p.line_of_business, l.period_month, sum(l.commission_amt) as commission_paid
      from {{ ref('stg_commission__ledger') }} l
      join {{ ref('stg_commission__policies') }} p using (policy_id)
     group by p.line_of_business, l.period_month
)
select ln.line_of_business,
       s.period_month,
       coalesce(e.policies_earning, 0)   as policies_earning,
       coalesce(e.earned_premium, 0)     as earned_premium,
       coalesce(r.claims_reported, 0)    as claims_reported,
       coalesce(r.reserve_reported, 0)   as reserve_reported,
       coalesce(pd.payments, 0)          as payments,
       coalesce(pd.paid_indemnity, 0)    as paid_indemnity,
       coalesce(pd.paid_expense, 0)      as paid_expense,
       coalesce(pd.salvage_recovered, 0) as salvage_recovered,
       coalesce(pd.paid_loss, 0)         as paid_loss,
       coalesce(cm.commission_paid, 0)   as commission_paid,
       case when coalesce(e.earned_premium, 0) > 0
            then round(coalesce(pd.paid_loss, 0) / e.earned_premium, 4) end as loss_ratio
  from lines ln
 cross join spine s
  left join earned e      on e.line_of_business = ln.line_of_business and e.period_month = s.period_month
  left join paid pd       on pd.line_of_business = ln.line_of_business and pd.period_month = s.period_month
  left join reported r    on r.line_of_business = ln.line_of_business and r.period_month = s.period_month
  left join commission cm on cm.line_of_business = ln.line_of_business and cm.period_month = s.period_month
