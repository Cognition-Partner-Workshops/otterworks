{{ config(tags=['audit']) }}
select 'reconciliation arithmetic' as violation
from {{ ref('audit_recon_final') }}
where business_dt = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
  and not (difference_count <=> source_count-target_count)
union all
select 'summary export count' from {{ ref('audit_summary_final') }}
where summary_id >= 10000000000 and (export_count <> 0 or event_count <= 0)
union all
select 'shared integration row' from {{ ref('audit_recon_final') }}
where recon_id = 21000000001
union all
select 'event type width' from {{ ref('audit_event') }}
where length(event_type) <> 12
union all
select 'disabled archive' from {{ ref('audit_event_archive') }}
where {{ 'false' if var('audit_archive_enabled', false) else 'true' }}
