{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_uniqueness']) }}
-- storage_quotas.id is unique within one export file (replays under another file name are out of scope)
select _file_name, id, count(*) as copies
from {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }}
group by 1, 2
having count(*) > 1
