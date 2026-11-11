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
    cast(IS_ACTIVE as CHAR(1)) as is_active,
    cast(PLAN_CODE as VARCHAR(10)) as plan_code,
    cast(START_DT as DATE) as start_dt,
    cast(END_DT as DATE) as end_dt,
    cast(STATUS_CD as VARCHAR(12)) as status_cd
from {{ source('billing', 'SUBSCRIPTION') }}
