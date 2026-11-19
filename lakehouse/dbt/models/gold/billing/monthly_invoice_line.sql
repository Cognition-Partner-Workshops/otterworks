select * from {{ ref('invoice_line') }}
where description is null or description not in ('Monthly subscription', 'Billing adjustment')
union all
select cast(300000000000 + h.invoice_id as bigint), h.invoice_id, 100,
       'Monthly subscription', 1, p.monthly_fee, p.monthly_fee
from {{ ref('invoice_hdr') }} h
join {{ ref('subscription') }} s on h.subscription_id = s.subscription_id
join {{ ref('plan_catalog') }} p on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
union all
select cast(400000000000 + a.adjustment_id as bigint), a.invoice_id, 200,
       'Billing adjustment', 1, a.amount, a.amount
from {{ ref('billing_adj') }} a
join {{ ref('invoice_hdr') }} h on a.invoice_id = h.invoice_id
join {{ ref('subscription') }} s on h.subscription_id = s.subscription_id
join {{ ref('plan_catalog') }} p on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
