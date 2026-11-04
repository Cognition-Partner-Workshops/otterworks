{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_row_count']) }}
-- business_rule: one row per account with a storage_quotas row whose admin_users status is not deleted,
-- taken from the newest export of each UTC export date
with exports as (
  select _export_id, convert_timezone('UTC', _exported_at)::date as snapshot_date
  from {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }}
  where _export_id is not null and _exported_at is not null
  qualify row_number() over (partition by snapshot_date order by _exported_at desc, _export_id desc) = 1
), expected as (
  select e.snapshot_date, count(distinct q.user_id) as expected_rows
  from exports e
  join {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }} q on q._export_id = e._export_id
  join {{ source('raw_doc_usage_dashboard', 'ADMIN_ADMIN_USERS') }} u on u._export_id = e._export_id and u.id = q.user_id
  where u.status <> 'deleted'
  group by 1
), actual as (
  select snapshot_date, count(*) as output_rows from {{ ref('doc_usage_dashboard') }} group by 1
)
select coalesce(e.snapshot_date, a.snapshot_date) as snapshot_date, e.expected_rows, a.output_rows
from expected e full outer join actual a on a.snapshot_date = e.snapshot_date
where e.expected_rows is null or a.output_rows is null or e.expected_rows <> a.output_rows
