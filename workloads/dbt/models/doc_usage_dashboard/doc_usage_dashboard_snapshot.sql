{{ config(materialized='incremental', incremental_strategy='append',
    pre_hook="{{ clear_changed_dates('usage_quotas','snapshot_date') }}",
    post_hook="{{ output_grants() }}") }}

with batches as (
 {{ latest_batches(ref('usage_quotas'), "convert_timezone('UTC', _exported_at)::date") }}
), counts as (
 select _export_id, owner_id, count(*) as active_document_count
 from {{ ref('usage_documents') }} where not is_deleted and not is_template
 group by _export_id, owner_id
)
select b.snapshot_date::date as snapshot_date,
 q.user_id::varchar(36) as account_id,
 q.tier::varchar(16) as tier, q.quota_bytes::number(19,0) as quota_bytes,
 q.used_bytes::number(19,0) as used_bytes,
 greatest(q.quota_bytes-q.used_bytes,0)::number(19,0) as remaining_bytes,
 round(q.used_bytes/q.quota_bytes*100,2)::number(7,2) as usage_pct,
 (case when q.used_bytes >= q.quota_bytes then 'over_quota'
 when q.used_bytes/q.quota_bytes >= 0.8 then 'near_limit' else 'ok' end)::varchar(16) as usage_band,
 coalesce(c.active_document_count,0)::number(10,0) as active_document_count
from batches b join {{ ref('usage_quotas') }} q on q._export_id=b._export_id
join {{ ref('usage_admin_users') }} u on u._export_id=b._export_id and u.id=q.user_id
left join counts c on c._export_id=b._export_id and c.owner_id=q.user_id
where u.status <> 'deleted'
