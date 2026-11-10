select
    cast(PAYMENT_ID as BIGINT) as payment_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(INVOICE_HDR_ID as BIGINT) as invoice_hdr_id,
    cast(PAYMENT_NUMBER as VARCHAR(30)) as payment_number,
    cast(PAYMENT_DATE as DATE) as payment_date,
    cast(AMOUNT as NUMBER(12,2)) as amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(METHOD as VARCHAR(30)) as method,
    cast(STATUS as VARCHAR(20)) as status,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at
from {{ source('billing', 'PAYMENT') }}
