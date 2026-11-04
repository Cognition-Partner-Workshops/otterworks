{{ config(tags=['dq', 'dq_churn_model', 'dq_row_count']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Business rule: per scored week, one row per account in that week's newest users export whose
-- admin_users status (same export) is not deleted and that was created before the Monday four weeks
-- before the scored week.
with exports as (
  select distinct _export_id, _exported_at,
         dateadd(day, -7, date_trunc('week', convert_timezone('UTC', _exported_at)::date))::date as week_start_date
  from {{ source('raw_churn_model', 'AUTH_USERS') }}
  where _export_id is not null and _exported_at is not null
), chosen as (
  select * from exports
  qualify row_number() over (partition by week_start_date order by _exported_at desc, _export_id desc) = 1
), eligible as (
  select c.week_start_date, count(distinct u.id) as eligible_accounts
  from chosen c
  join {{ source('raw_churn_model', 'AUTH_USERS') }} u on u._export_id = c._export_id
  join {{ source('raw_churn_model', 'ADMIN_ADMIN_USERS') }} a on a._export_id = c._export_id and a.id = u.id
  where a.status <> 'deleted' and u.created_at < dateadd(day, -28, c.week_start_date)
  group by 1
), scored as (
  select week_start_date, count(*) as output_rows from {{ ref('churn_model') }} group by 1
)
select coalesce(s.week_start_date, e.week_start_date) as week_start_date,
       coalesce(s.output_rows, 0) as output_rows, coalesce(e.eligible_accounts, 0) as eligible_accounts
from scored s full outer join eligible e on e.week_start_date = s.week_start_date
where coalesce(s.output_rows, 0) <> coalesce(e.eligible_accounts, 0)
