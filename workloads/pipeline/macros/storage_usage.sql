{% macro storage_usage(quotas, accounts, documents) %}
with document_counts as (
  select _snapshot_date, owner_id, count(*) as active_document_count
  from {{ documents }} where not is_deleted and not is_template
  group by 1,2
), measured as (
  select q._snapshot_date::date as snapshot_date, q.user_id::varchar(36) as account_id,
    a.email::varchar(255) as account_email, q.tier::varchar(16) as tier,
    q.quota_bytes::number(19,0) as quota_bytes, q.used_bytes::number(19,0) as used_bytes,
    greatest(q.quota_bytes-q.used_bytes,0)::number(19,0) as remaining_bytes,
    round(q.used_bytes / nullif(q.quota_bytes,0) * 100,2)::number(7,2) as usage_pct,
    coalesce(d.active_document_count,0)::number(10,0) as active_document_count
  from {{ quotas }} q join {{ accounts }} a
    on q.user_id=a.id and q._snapshot_date=a._snapshot_date
  left join document_counts d on d.owner_id=q.user_id and d._snapshot_date=q._snapshot_date
  where a.status <> 'deleted'
)
select snapshot_date, account_id, account_email, tier, quota_bytes, used_bytes, remaining_bytes, usage_pct,
  case when quota_bytes=0 then 'no_quota' when used_bytes>=quota_bytes then 'over_quota'
    when usage_pct>=80 then 'near_limit' else 'ok' end::varchar(16) as usage_band,
  active_document_count from measured
{% endmacro %}
