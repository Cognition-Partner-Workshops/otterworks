{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_freshness']) }}
-- spec output_columns: snapshot_date = "UTC date of the admin-service export"; the newest export's date must be on the dashboard
with newest_export as (
  select max(convert_timezone('UTC', _exported_at)::date) as export_date
  from {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }}
), newest_snapshot as (
  select max(snapshot_date) as snapshot_date from {{ ref('doc_usage_dashboard') }}
)
select e.export_date, s.snapshot_date
from newest_export e cross join newest_snapshot s
where s.snapshot_date is null or s.snapshot_date < e.export_date
