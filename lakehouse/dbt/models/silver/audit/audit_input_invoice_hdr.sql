{{ config(materialized='ephemeral') }}
select
    cast(invoice_id as bigint) as invoice_id,
    cast(customer_id as bigint) as customer_id,
    cast(subscription_id as bigint) as subscription_id,
    cast(invoice_dt as date) as invoice_dt,
    cast(bill_dt as date) as bill_dt,
    cast(period_start_dt as date) as period_start_dt,
    {{ legacy_text('currency_cd', 3, true) }} as currency_cd,
    cast(total_amount as decimal(18,2)) as total_amount,
    {{ legacy_text('invoice_number', 32) }} as invoice_number,
    cast(tax_rate_id as bigint) as tax_rate_id,
    cast(subtotal_amount as decimal(18,2)) as subtotal_amount,
    cast(tax_amount as decimal(18,2)) as tax_amount,
    {{ legacy_text('invoice_period', 7, true) }} as invoice_period,
    cast(period_key as int) as period_key,
    cast(prior_period_end_dt as date) as prior_period_end_dt,
    cast(invoice_month as int) as invoice_month,
    {{ legacy_text('period_closed_cd', 1, true) }} as period_closed_cd,
    cast(currency_control_total as decimal(18,2)) as currency_control_total
from {{ source('bronze_billing', 'invoice_hdr') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
