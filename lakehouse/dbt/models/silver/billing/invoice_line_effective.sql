{{ config(tags=['storage_monthly']) }}
select * from {{ ref('invoice_line') }}
where description is null or rtrim(description) <> 'Monthly storage'
union all
select cast(11000000000 + u.customer_id as bigint), i.invoice_id, 900, 'Monthly storage', 1,
       cast(cast(u.units as decimal(20,4)) / 1073741824 * 0.25 as decimal(14,2)),
       cast(cast(u.units as decimal(20,4)) / 1073741824 * 0.25 as decimal(14,2))
from {{ ref('usage_daily_effective') }} u
join (select customer_id, min(invoice_id) as invoice_id
      from {{ ref('invoice_hdr') }} group by customer_id) i on u.customer_id = i.customer_id
where upper(rtrim(u.usage_type)) = 'STORAGE'
