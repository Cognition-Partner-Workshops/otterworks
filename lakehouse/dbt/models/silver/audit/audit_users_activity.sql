{{ config(materialized='ephemeral') }}
select * from {{ ref('audit_input_user_activity_daily') }} where activity_id < 10000000000
union all
select cast(10000000000+user_id as bigint), user_id, to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), cast(count(*) as int), cast(0 as int)
from {{ ref('audit_input_login_event') }} where cast(login_ts as date) = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') group by user_id
