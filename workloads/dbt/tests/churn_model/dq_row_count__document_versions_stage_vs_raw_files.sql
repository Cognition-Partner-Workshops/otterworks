{{ config(tags=['dq', 'dq_churn_model', 'dq_row_count']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Rows per stage file must equal rows per _file_name in RAW.DOCUMENT_DOCUMENT_VERSIONS: the load lost or invented nothing.
with staged as (
  select metadata$filename as file_name, count(*) as stage_rows
  from @{{ target.database }}.RAW.POSTGRES_FILES/document_versions/ (file_format => '{{ target.database }}.RAW.POSTGRES_CSV')
  group by 1
), loaded as (
  select _file_name as file_name, count(*) as raw_rows
  from {{ source('raw_churn_model', 'DOCUMENT_DOCUMENT_VERSIONS') }}
  group by 1
)
select coalesce(s.file_name, l.file_name) as file_name, coalesce(s.stage_rows, 0) as stage_rows, coalesce(l.raw_rows, 0) as raw_rows
from staged s full outer join loaded l on l.file_name = s.file_name
where coalesce(s.stage_rows, 0) <> coalesce(l.raw_rows, 0)
