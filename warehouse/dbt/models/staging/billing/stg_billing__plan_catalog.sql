select
    cast(PLAN_CATALOG_ID as BIGINT) as plan_catalog_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(PLAN_CODE as VARCHAR(30)) as plan_code,
    cast(PLAN_NAME as VARCHAR(80)) as plan_name,
    cast(MONTHLY_PRICE as NUMBER(12,2)) as monthly_price,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(STORAGE_LIMIT_GB as INTEGER) as storage_limit_gb,
    cast(SEAT_LIMIT as INTEGER) as seat_limit,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active,
    cast(coalesce(PLAN_ID, PLAN_CATALOG_ID) as BIGINT) as plan_id,
    cast(MONTHLY_FEE as NUMBER(12,2)) as monthly_fee,
    cast(CURRENCY_CD as VARCHAR(3)) as currency_cd
from {{ source('billing', 'PLAN_CATALOG') }}
