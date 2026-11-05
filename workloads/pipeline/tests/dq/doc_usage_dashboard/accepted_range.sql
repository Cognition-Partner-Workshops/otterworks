{{ config(tags=['dq_doc_usage_dashboard']) }}
select 'accepted_range: invalid storage values for ' || coalesce(account_id,'NULL')
  || ' snapshot=' || coalesce(snapshot_date::varchar,'NULL') as failure
from {{ ref('account_storage_usage') }}
where snapshot_date is null or account_id is null or account_email is null or tier is null
  or quota_bytes is null or used_bytes is null or remaining_bytes is null
  or usage_band is null or active_document_count is null
  or tier not in ('free','basic','pro','enterprise')
  or usage_band not in ('over_quota','near_limit','ok','no_quota')
  or quota_bytes<0 or used_bytes<0 or remaining_bytes<0 or active_document_count<0
  or remaining_bytes<>greatest(quota_bytes-used_bytes,0)
  or usage_pct is distinct from round(used_bytes/nullif(quota_bytes,0)*100,2)
  or usage_band is distinct from case when quota_bytes=0 then 'no_quota'
    when used_bytes>=quota_bytes then 'over_quota'
    when round(used_bytes/nullif(quota_bytes,0)*100,2)>=80 then 'near_limit' else 'ok' end
