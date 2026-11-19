{{ config(materialized='ephemeral') }}
select invoice_line_id from {{ ref('audit_input_invoice_line') }}
where description is null or description not in ('Monthly storage', 'Monthly subscription', 'Billing adjustment')
union all
select cast(11000000000+u.customer_id as bigint) from {{ ref('audit_storage_customers') }} u
join (select customer_id, min(invoice_id) as invoice_id from {{ ref('audit_input_invoice_hdr') }} group by customer_id) i on u.customer_id=i.customer_id
union all
select cast(300000000000+invoice_id as bigint) from {{ ref('audit_invoice_matches') }}
union all
select cast(400000000000+a.adjustment_id as bigint)
from {{ ref('audit_input_billing_adj') }} a join {{ ref('audit_invoice_matches') }} h on a.invoice_id=h.invoice_id
