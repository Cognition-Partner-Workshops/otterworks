-- DER Normalise timestamps on plans: included_bytes is included_units binary GiB and
-- overage_cents_per_gb is the per-GB rate in whole cents.
select id, included_units, included_bytes, overage_rate, overage_cents_per_gb
from {{ ref('stg_billing_plans') }}
where included_bytes is distinct from included_units::number(19, 0) * 1073741824
    or overage_cents_per_gb is distinct from round(overage_rate * 100, 0)::integer
