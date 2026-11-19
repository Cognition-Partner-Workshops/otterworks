with accounts as (
    select 1 line_no, 1200 gl_account_id union all select 2, 4000
    union all select 3, 4100 union all select 4, 2200
), postings as (
    select h.invoice_id, cast(null as bigint) credit_note_id, a.line_no, a.gl_account_id, h.currency_cd,
           case when a.gl_account_id = 1200 then h.total_amount
                when a.gl_account_id = 4000 then -p.monthly_fee
                when a.gl_account_id = 4100 then -(h.subtotal_amount - p.monthly_fee)
                else -h.tax_amount end signed_amount
    from {{ ref('monthly_invoice_hdr') }} h
    join {{ ref('subscription') }} s on h.subscription_id = s.subscription_id
    join {{ ref('plan_catalog') }} p on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
    cross join accounts a
    where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
      and h.currency_cd is not null
), reversals as (
    select h.invoice_id, cr.credit_note_id, a.line_no, a.gl_account_id, h.currency_cd,
           case when a.gl_account_id = 1200 then -cr.amount
                when a.gl_account_id = 4100 then round(cr.amount / (1 + t.rate), 2)
                else cr.amount - round(cr.amount / (1 + t.rate), 2) end signed_amount
    from {{ ref('credit_note') }} cr
    join {{ ref('monthly_invoice_hdr') }} h on cr.invoice_id = h.invoice_id
    join {{ ref('subscription') }} s on h.subscription_id = s.subscription_id
    join {{ ref('plan_catalog') }} p on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
    join {{ ref('tax_rate') }} t on h.tax_rate_id = t.tax_rate_id
    cross join (select 1 line_no, 1200 gl_account_id union all select 2, 4100 union all select 3, 2200) a
    where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
      and cr.credit_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
      and h.currency_cd is not null
), generated as (
    select *, 'Monthly invoice posting' description from postings
    union all select *, 'Credit note reversal' description from reversals
)
select * from {{ ref('gl_journal_line') }}
where posting_dt is null
   or posting_dt < trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM')
   or posting_dt >= add_months(trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM'), 1)
union all
select cast(cast(substring('{{ env_var("BUSINESS_DATE") }}', 1, 6) as bigint) * 1000000000000
            + case when credit_note_id is null then invoice_id * 10
                   else 500000000000 + credit_note_id * 10 end + line_no as bigint),
       invoice_id, credit_note_id, cast(gl_account_id as bigint),
       to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), currency_cd,
       cast(case when signed_amount >= 0 then signed_amount else 0 end as decimal(14,2)),
       cast(case when signed_amount < 0 then -signed_amount else 0 end as decimal(14,2)), description
from generated
