-- rpt_audit_user_activity: the dataset of source/reports/rpt_audit_user_activity.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    user_id,
    action,
    resource_type,
    resource_id,
    event_ts_utc
from {{ ref('rollup_audit') }}
