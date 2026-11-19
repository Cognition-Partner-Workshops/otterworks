with combined as (
    select * from {{ ref('audit_recon') }}
    where recon_id not between 20000000001 and 20000000037
      and recon_id <> 21000000001
    union all
    select recon_id, to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), cast(0 as bigint), source_count, target_count, source_count-target_count
    from {{ ref('audit_count_inputs') }}
)
select recon_id, business_dt, customer_id, source_count, target_count,
       case when business_dt = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') then source_count-target_count else difference_count end as difference_count
from combined
