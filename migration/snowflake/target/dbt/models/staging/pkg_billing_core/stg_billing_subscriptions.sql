-- pkg_billing_core, DFT Load stg_billing_subscriptions: billing_subscriptions.csv -> stg.stg_billing_subscriptions.
-- (DT_DBTIMESTAMP2,7) casts land in date columns, so any time of day is dropped.
with subscriptions as (
    select * from {{ source('pkg_billing_core', 'EXT_BILLING_SUBSCRIPTIONS') }}
)

select
    nullif(id, '')::varchar(36) as id,
    nullif(tenant_id, '')::varchar(36) as tenant_id,
    nullif(plan_id, '')::varchar(36) as plan_id,
    nullif(starts_on, '')::timestamp_ntz::date as starts_on,
    nullif(ends_on, '')::timestamp_ntz::date as ends_on,
    nullif(status, '')::varchar(20) as status,
    nullif(suspended_on, '')::timestamp_ntz::date as suspended_on,
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz as extracted_at,
    'legacy-billing'::varchar(40) as source_system
from subscriptions
