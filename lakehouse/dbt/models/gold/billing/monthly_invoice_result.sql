select count(*) as n from {{ ref('monthly_invoice_hdr') }} h
join {{ ref('subscription') }} s on h.subscription_id = s.subscription_id
join {{ ref('plan_catalog') }} p on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
join {{ ref('tax_rate') }} t on h.tax_rate_id = t.tax_rate_id
where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
