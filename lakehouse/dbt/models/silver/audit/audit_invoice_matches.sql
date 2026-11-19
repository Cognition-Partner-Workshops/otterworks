{{ config(materialized='ephemeral') }}
select h.invoice_id
from {{ ref('audit_input_invoice_hdr') }} h
join {{ ref('audit_input_subscription') }} s on h.subscription_id=s.subscription_id
join {{ ref('audit_input_plan_catalog') }} p on upper(rtrim(s.plan_code))=upper(rtrim(p.plan_code))
where h.invoice_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
