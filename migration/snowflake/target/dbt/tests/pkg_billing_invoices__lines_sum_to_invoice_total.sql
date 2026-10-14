-- Every invoice's lines add up to the header total the Lookup copies onto each line.
select invoice_id, max(total) as total, sum(amount) as line_sum
from {{ ref('stg_billing_invoices') }}
group by invoice_id
having sum(amount) <> max(total) or max(subtotal) + max(tax) <> max(total)
