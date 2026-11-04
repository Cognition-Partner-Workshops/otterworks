{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_uniqueness']) }}
-- spec inputs: storage_quotas.user_id is "uuid, unique, the account", so unique within one export file
select _file_name, user_id, count(*) as copies
from {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }}
group by 1, 2
having count(*) > 1
