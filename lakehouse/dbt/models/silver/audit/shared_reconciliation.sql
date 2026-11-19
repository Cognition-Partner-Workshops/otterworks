{{ config(tags=['shared_reconcile']) }}
select cast(21000000001 as bigint) as recon_id,
       to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') as business_dt,
       cast(0 as bigint) as customer_id, s.n as source_count, t.n as target_count,
       s.n-t.n as difference_count
from (select count(*) as n from {{ ref('stg_storage_usage_daily') }}) s
cross join (select count(*) as n from {{ ref('storage_usage_daily') }}) t
