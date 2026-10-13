-- dbo.usp_rate_overage: rates storage over the plan allowance on each tenant's daily storage row.
--
-- The legacy cursor computes overage_gb = (bytes_used - included_bytes) / 1073741824 in bigint
-- arithmetic, so every partial GB over the allowance is dropped before it is priced:
-- 1.99 GB over is billed as 1 GB, 0.99 GB over as nothing. This model prorates the overage to
-- the byte: overage_gb to three decimals and overage_cents rounded to the cent from the exact
-- bytes. Set the var legacy_overage_whole_gb_truncation to true to reproduce the legacy
-- whole-GB numbers exactly while Finance decides (gate/out/ledger.md, rate_overage).
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

{%- set legacy_truncation = var('legacy_overage_whole_gb_truncation', false) %}
{%- set bytes_per_gb = 1073741824 %}

with storage as (
    select
        storage.business_date,
        storage.tenant_id,
        storage.plan_id,
        storage.bytes_used,
        storage.included_bytes,
        plans.plan_id as rated_plan_id,
        plans.overage_cents_per_gb,
        iff(storage.bytes_used > storage.included_bytes, storage.bytes_used - storage.included_bytes, 0)
            as overage_bytes
    from {{ ref('rollup_storage_daily') }} as storage
    left join {{ ref('dim_plan') }} as plans
        on plans.plan_id = storage.plan_id
    where {{ for_business_date('storage.business_date') }}
)

select
    business_date,
    tenant_id,
    plan_id,
    bytes_used,
    included_bytes,
    overage_cents_per_gb,
    {% if legacy_truncation -%}
    iff(rated_plan_id is null, null, trunc(overage_bytes / {{ bytes_per_gb }})::number(38, 0))
    {%- else -%}
    iff(rated_plan_id is null, null, round(overage_bytes / {{ bytes_per_gb }}, 3)::number(18, 3))
    {%- endif %} as overage_gb,
    {% if legacy_truncation -%}
    iff(rated_plan_id is null, null, trunc(overage_bytes / {{ bytes_per_gb }}) * overage_cents_per_gb)::number(38, 0)
    {%- else -%}
    iff(rated_plan_id is null, null, round(overage_bytes * overage_cents_per_gb / {{ bytes_per_gb }}, 0))::number(38, 0)
    {%- endif %} as overage_cents,
    current_timestamp()::timestamp_ntz as loaded_at
from storage
