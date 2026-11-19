select * from {{ ref('audit_daily_summary') }} where summary_id < 10000000000
union all
select cast(10000000000 + customer_id as bigint), to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), customer_id,
       count(*), cast(0 as int)
from {{ ref('audit_event') }}
where cast(event_ts as date) = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
group by customer_id
