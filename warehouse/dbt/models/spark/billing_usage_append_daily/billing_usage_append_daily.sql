{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='USAGE_DATE') }}

-- The first build backfills every landed usage date; later runs replace only the latest date.
select USAGE_ID, CUSTOMER_ID, USAGE_DATE, UNITS, AMOUNT
from {{ source('spark_billing', 'USAGE_DAILY') }}
{% if is_incremental() %}
where USAGE_DATE = (
    select max(USAGE_DATE)
    from {{ source('spark_billing', 'USAGE_DAILY') }}
)
{% endif %}
