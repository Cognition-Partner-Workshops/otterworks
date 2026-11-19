select a.customer_id, a.account_name, i.invoice_id, i.invoice_dt, i.currency_cd, i.total_amount
from {{ ref('customer_account') }} a join {{ ref('closed_invoice_hdr') }} i on a.customer_id = i.customer_id
