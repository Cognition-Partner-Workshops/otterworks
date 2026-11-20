{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='USAGE_DATE') }}

-- Match the legacy job's latest-date batch on both initial and incremental builds.
select USAGE_ID, CUSTOMER_ID, USAGE_DATE, UNITS, AMOUNT
from {{ source('spark_billing', 'USAGE_DAILY') }}
where USAGE_DATE = (
    select max(USAGE_DATE)
    from {{ source('spark_billing', 'USAGE_DAILY') }}
)
