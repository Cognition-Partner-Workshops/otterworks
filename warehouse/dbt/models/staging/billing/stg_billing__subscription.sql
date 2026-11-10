select
    cast(SUBSCRIPTION_ID as BIGINT) as subscription_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(PLAN_CATALOG_ID as BIGINT) as plan_catalog_id,
    cast(START_DATE as DATE) as start_date,
    cast(NEXT_BILL_DATE as DATE) as next_bill_date,
    cast(SEAT_COUNT as INTEGER) as seat_count,
    cast(STATUS as VARCHAR(20)) as status,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active
from {{ source('billing', 'SUBSCRIPTION') }}
