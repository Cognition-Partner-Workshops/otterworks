{{ config(tags=['dq', 'dq_churn_model', 'dq_row_count']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Each staging model's rows per _export_id must equal the distinct source ids of that export.
{% set inputs = [('users', 'AUTH_USERS', 'churn_users'), ('admin_users', 'ADMIN_ADMIN_USERS', 'churn_admin_users'), ('document_versions', 'DOCUMENT_DOCUMENT_VERSIONS', 'churn_versions')] %}
{% for input, raw, staging in inputs %}
select '{{ input }}' as input, coalesce(s._export_id, r._export_id) as _export_id,
       coalesce(s.staging_rows, 0) as staging_rows, coalesce(r.source_keys, 0) as source_keys
from (select _export_id, count(*) as staging_rows from {{ ref(staging) }} group by 1) s
full outer join (
  select _export_id, count(distinct id) as source_keys
  from {{ source('raw_churn_model', raw) }} where _export_id is not null group by 1
) r on r._export_id = s._export_id
where coalesce(s.staging_rows, 0) <> coalesce(r.source_keys, 0)
{% if not loop.last %}union all{% endif %}
{% endfor %}
