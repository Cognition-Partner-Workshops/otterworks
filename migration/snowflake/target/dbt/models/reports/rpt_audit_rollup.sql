-- rpt_audit_rollup: the dataset of source/reports/rpt_audit_rollup.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    action,
    resource_type,
    event_count,
    distinct_users,
    first_event_utc,
    last_event_utc
from {{ ref('build_mart_audit') }}
