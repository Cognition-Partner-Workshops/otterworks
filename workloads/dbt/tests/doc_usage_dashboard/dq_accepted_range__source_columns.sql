{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_accepted_range']) }}
-- spec inputs: storage_quotas quota_bytes > 0, used_bytes >= 0, tier in free/basic/pro/enterprise;
-- admin_users status in active/suspended/deleted (AdminUser::STATUSES)
select 'storage_quotas' as input, _file_name, id, 'quota_bytes/used_bytes/tier' as rule
from {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }}
where quota_bytes is null or quota_bytes <= 0 or used_bytes is null or used_bytes < 0
  or tier is null or tier not in ('free', 'basic', 'pro', 'enterprise')
union all
select 'admin_users', _file_name, id, 'status'
from {{ source('raw_doc_usage_dashboard', 'ADMIN_ADMIN_USERS') }}
where status is null or status not in ('active', 'suspended', 'deleted')
