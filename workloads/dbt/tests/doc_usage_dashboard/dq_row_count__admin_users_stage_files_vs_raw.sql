{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_row_count']) }}
-- every staged admin_users export file is landed in RAW.ADMIN_ADMIN_USERS with exactly its rows
with staged as (
  select metadata$filename as file_name, count(*) as staged_rows
  from @{{ target.database }}.RAW.POSTGRES_FILES/admin_users/ (file_format => '{{ target.database }}.RAW.POSTGRES_CSV')
  group by 1
), landed as (
  select _file_name as file_name, count(*) as landed_rows
  from {{ source('raw_doc_usage_dashboard', 'ADMIN_ADMIN_USERS') }}
  group by 1
)
select coalesce(s.file_name, l.file_name) as file_name, s.staged_rows, l.landed_rows
from staged s full outer join landed l on l.file_name = s.file_name
where s.staged_rows is null or l.landed_rows is null or s.staged_rows <> l.landed_rows
