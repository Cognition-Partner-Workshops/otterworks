select min(currency_cd) as currency_cd, count(*) as invoice_count, sum(total_amount) as total_amount
from {{ ref('invoice_hdr') }} group by lower(rtrim(currency_cd))
