select
    cast(USAGE_DAILY_ID as BIGINT) as usage_daily_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(USAGE_DATE as DATE) as usage_date,
    cast(QUANTITY as INTEGER) as quantity,
    cast(UNIT_PRICE as NUMBER(12,2)) as unit_price,
    cast(AMOUNT as NUMBER(12,2)) as amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active,
    cast(coalesce(USAGE_ID, USAGE_DAILY_ID) as BIGINT) as usage_id,
    cast(SUBSCRIPTION_ID as BIGINT) as subscription_id,
    cast(USAGE_DT as DATE) as usage_dt,
    cast(UNITS as BIGINT) as units,
    cast(USAGE_TYPE as VARCHAR(12)) as usage_type
from {{ source('billing', 'USAGE_DAILY') }}
