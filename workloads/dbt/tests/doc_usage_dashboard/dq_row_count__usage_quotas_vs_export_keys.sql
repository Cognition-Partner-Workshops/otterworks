{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_row_count']) }}
-- staging usage_quotas keeps exactly one row per distinct storage_quotas.id of each export
with source_keys as (
  select _export_id, count(distinct id) as source_keys
  from {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }}
  where _export_id is not null
  group by 1
), staged as (
  select _export_id, count(*) as staged_rows
  from {{ ref('usage_quotas') }}
  group by 1
)
select coalesce(k._export_id, s._export_id) as _export_id, k.source_keys, s.staged_rows
from source_keys k full outer join staged s on s._export_id = k._export_id
where k.source_keys is null or s.staged_rows is null or k.source_keys <> s.staged_rows
