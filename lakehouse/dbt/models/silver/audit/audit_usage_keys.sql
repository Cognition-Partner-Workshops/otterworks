{{ config(materialized='ephemeral') }}
select usage_id from {{ ref('audit_input_usage_daily') }}
where usage_type is null or rtrim(upper(usage_type)) <> 'STORAGE'
union all
select cast(10000000000+customer_id as bigint) from {{ ref('audit_storage_customers') }}
