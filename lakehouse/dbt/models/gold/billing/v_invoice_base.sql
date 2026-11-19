select customer_id, account_name, invoice_id, invoice_dt, currency_cd, total_amount
from {{ ref('v_account_invoices') }}
