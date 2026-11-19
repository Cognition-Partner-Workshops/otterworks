with amounts as (
    select h.invoice_id, coalesce(sum(l.line_amount), 0) as subtotal_amount,
           round(coalesce(sum(l.line_amount), 0) * max(t.rate), 2) as tax_amount
    from {{ ref('invoice_hdr') }} h
    join {{ ref('subscription') }} s on h.subscription_id = s.subscription_id
    join {{ ref('plan_catalog') }} p on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
    join {{ ref('tax_rate') }} t on h.tax_rate_id = t.tax_rate_id
    left join {{ ref('monthly_invoice_line') }} l on h.invoice_id = l.invoice_id
    where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
    group by h.invoice_id
), revised as (
    select h.invoice_id, h.customer_id, h.subscription_id, h.invoice_dt, h.bill_dt,
           h.period_start_dt, h.currency_cd,
           cast(case when a.invoice_id is not null then a.subtotal_amount + a.tax_amount
                     else h.total_amount end as decimal(14,2)) as total_amount,
           h.invoice_number, h.tax_rate_id,
           cast(case when a.invoice_id is not null then a.subtotal_amount
                     else h.subtotal_amount end as decimal(14,2)) as subtotal_amount,
           cast(case when a.invoice_id is not null then a.tax_amount
                     else h.tax_amount end as decimal(14,2)) as tax_amount,
           h.invoice_period, h.period_key, h.prior_period_end_dt, h.invoice_month,
           h.period_closed_cd
    from {{ ref('invoice_hdr') }} h left join amounts a on h.invoice_id = a.invoice_id
)
select *, cast(sum(total_amount) over (partition by lower(rtrim(currency_cd))) as decimal(14,2)) as currency_control_total
from revised
