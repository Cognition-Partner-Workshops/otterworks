-- pkg_billing_core, DFT Load stg_billing_plans: billing_plans.csv -> stg.stg_billing_plans.
-- Legacy behaviour kept on purpose (see gate/out/staging/pkg_billing_core.md):
--   active = (LOWER(active) == "true") although the file carries t/f, so every plan lands inactive;
--   overage_cents_per_gb = (DT_I4)ROUND(overage_rate * 100, 0), half-up to whole cents.
with plans as (
    select * from {{ source('pkg_billing_core', 'EXT_BILLING_PLANS') }}
)

select
    nullif(id, '')::varchar(36) as id,
    nullif(code, '')::varchar(40) as code,
    nullif(tier, '')::varchar(20) as tier,
    nullif(monthly_fee, '')::number(12, 2) as monthly_fee,
    nullif(included_units, '')::integer as included_units,
    nullif(overage_rate, '')::number(12, 6) as overage_rate,
    coalesce(lower(nullif(active, '')) = 'true', false) as active,
    (trunc(nullif(included_units, '')::double)::number(19, 0) * 1073741824)::number(19, 0)
        as included_bytes,
    trunc(round(nullif(overage_rate, '')::double * 100, 0))::integer as overage_cents_per_gb,
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz as extracted_at,
    'legacy-billing'::varchar(40) as source_system
from plans
