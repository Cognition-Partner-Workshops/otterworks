-- pkg_billing_core has no filter or Conditional Split and the Lookup keeps unmatched rows, so
-- every staging model has exactly one row per row of its flat file.
with counts as (
    select 'stg_billing_tenants' as model,
        (select count(*) from {{ source('pkg_billing_core', 'EXT_BILLING_TENANTS') }}) as file_rows,
        (select count(*) from {{ ref('stg_billing_tenants') }}) as model_rows
    union all
    select 'stg_billing_plans',
        (select count(*) from {{ source('pkg_billing_core', 'EXT_BILLING_PLANS') }}),
        (select count(*) from {{ ref('stg_billing_plans') }})
    union all
    select 'stg_billing_subscriptions',
        (select count(*) from {{ source('pkg_billing_core', 'EXT_BILLING_SUBSCRIPTIONS') }}),
        (select count(*) from {{ ref('stg_billing_subscriptions') }})
)

select * from counts where file_rows <> model_rows
