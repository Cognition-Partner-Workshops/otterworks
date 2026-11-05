{{ config(materialized='view', post_hook="{{ output_grants() }}") }}

select s.snapshot_date, s.account_id, u.email::varchar(255) as account_email,
 s.tier, s.quota_bytes, s.used_bytes, s.remaining_bytes,
 s.usage_pct, s.usage_band, s.active_document_count
from {{ ref('doc_usage_dashboard_snapshot') }} s
join {{ ref('usage_admin_users') }} u on u.id = s.account_id
 and convert_timezone('UTC',u._exported_at)::date <= s.snapshot_date
qualify row_number() over (
 partition by s.snapshot_date,s.account_id
 order by u._exported_at desc,u._export_id desc
) = 1
