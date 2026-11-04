{#- Fails with one row per (snapshot_date, account_id) where the dashboard and admin-service disagree.
    Admin side for a date = the last admin-service export with that UTC date: storage_quotas of every
    account whose admin_users status is not deleted, with StorageQuota#usage_percentage, #remaining_bytes
    and #over_quota?. Written independently of latest_batches so a batch-selection bug is caught too. -#}
{% test matches_admin_service(model, quotas, admin_users) %}
with exports as (
 select snapshot_date, _export_id from (
  select convert_timezone('UTC', _exported_at)::date as snapshot_date, _export_id, _exported_at
  from {{ quotas }} group by 1, 2, 3
 )
 qualify row_number() over (partition by snapshot_date order by _exported_at desc, _export_id desc) = 1
), admin as (
 select e.snapshot_date, q.user_id::varchar(36) as account_id, q.quota_bytes, q.used_bytes,
  greatest(q.quota_bytes - q.used_bytes, 0) as remaining_bytes,
  round(q.used_bytes / q.quota_bytes * 100, 2) as usage_percentage,
  q.used_bytes >= q.quota_bytes as over_quota
 from exports e
 join {{ quotas }} q on q._export_id = e._export_id
 join {{ admin_users }} u on u._export_id = e._export_id and u.id = q.user_id
 where u.status <> 'deleted'
)
select coalesce(a.snapshot_date, d.snapshot_date) as snapshot_date,
 coalesce(a.account_id, d.account_id) as account_id,
 a.used_bytes as admin_used_bytes, d.used_bytes as dashboard_used_bytes,
 a.quota_bytes as admin_quota_bytes, d.quota_bytes as dashboard_quota_bytes,
 a.usage_percentage as admin_usage_percentage, d.usage_pct as dashboard_usage_pct
from admin a
full outer join {{ model }} d on d.snapshot_date = a.snapshot_date and d.account_id = a.account_id
where a.account_id is null or d.account_id is null
 or a.used_bytes <> d.used_bytes or a.quota_bytes <> d.quota_bytes
 or a.remaining_bytes <> d.remaining_bytes or a.usage_percentage <> d.usage_pct
 or a.over_quota <> (d.usage_band = 'over_quota')
{% endtest %}
