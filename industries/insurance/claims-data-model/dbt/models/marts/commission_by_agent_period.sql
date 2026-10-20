-- Commission earned per agent per ledger period, from the Oracle ledger as COMMISSION_PKG wrote it.
-- No re-rounding: every ledger row is already ROUND(..., 2) in Oracle (half away from zero).
select l.agent_id,
       a.agent_code,
       a.full_name,
       l.period_month,
       count(*)              as ledger_rows,
       count(distinct l.policy_id) as policies,
       sum(l.commission_amt) as total_commission
  from {{ ref('stg_commission__ledger') }} l
  join {{ ref('stg_commission__agents') }} a using (agent_id)
 group by l.agent_id, a.agent_code, a.full_name, l.period_month
