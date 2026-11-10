select
    cast(INVOICE_HDR_ID as BIGINT) as invoice_hdr_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(INVOICE_NUMBER as VARCHAR(30)) as invoice_number,
    cast(INVOICE_DATE as DATE) as invoice_date,
    cast(DUE_DATE as DATE) as due_date,
    cast(SUBTOTAL_AMOUNT as NUMBER(12,2)) as subtotal_amount,
    cast(TAX_AMOUNT as NUMBER(12,2)) as tax_amount,
    cast(TOTAL_AMOUNT as NUMBER(12,2)) as total_amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(STATUS as VARCHAR(20)) as status
from {{ source('billing', 'INVOICE_HDR') }}
