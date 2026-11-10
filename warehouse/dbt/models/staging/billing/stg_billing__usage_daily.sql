select
    cast(USAGE_DAILY_ID as BIGINT) as usage_daily_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(USAGE_DATE as DATE) as usage_date,
    cast(QUANTITY as INTEGER) as quantity,
    cast(UNIT_PRICE as NUMBER(12,2)) as unit_price,
    cast(AMOUNT as NUMBER(12,2)) as amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active
from {{ source('billing', 'USAGE_DAILY') }}
