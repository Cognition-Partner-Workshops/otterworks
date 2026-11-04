{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_accepted_range']) }}
-- spec output_columns / business_rule arithmetic, near_limit_ratio 0.80 on the unrounded ratio
{% set near_limit_ratio = 0.80 %}
select snapshot_date, account_id, quota_bytes, used_bytes, remaining_bytes, usage_pct, usage_band
from {{ ref('doc_usage_dashboard') }}
where remaining_bytes <> greatest(quota_bytes - used_bytes, 0)
  or usage_pct <> round(used_bytes / quota_bytes * 100, 2)
  or usage_band <> case
       when used_bytes >= quota_bytes then 'over_quota'
       when used_bytes / quota_bytes >= {{ near_limit_ratio }} then 'near_limit'
       else 'ok' end
