{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_uniqueness']) }}
-- admin_users.id is unique within one export file (replays under another file name are out of scope)
select _file_name, id, count(*) as copies
from {{ source('raw_doc_usage_dashboard', 'ADMIN_ADMIN_USERS') }}
group by 1, 2
having count(*) > 1
