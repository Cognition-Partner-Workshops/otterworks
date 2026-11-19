{{ config(tags=['storage_monthly']) }}
select * from {{ ref('usage_daily') }}
where usage_type is null or upper(rtrim(usage_type)) <> 'STORAGE'
union all
select cast(10000000000 + u.customer_id as bigint), u.customer_id, s.subscription_id,
       to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), cast(u.bytes_used as bigint),
       rpad('STORAGE', 12, ' ')
from {{ ref('m_storage_totals') }} u
join (select customer_id, min(subscription_id) as subscription_id
      from {{ ref('subscription') }} group by customer_id) s on u.customer_id = s.customer_id
