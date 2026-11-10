select
    cast(TAX_RATE_ID as BIGINT) as tax_rate_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(COUNTRY_CODE as CHAR(2)) as country_code,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(TAX_NAME as VARCHAR(80)) as tax_name,
    cast(RATE as NUMBER(8,4)) as rate,
    cast(EFFECTIVE_DATE as DATE) as effective_date,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active
from {{ source('billing', 'TAX_RATE') }}
