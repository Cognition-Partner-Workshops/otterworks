select
    cast(INVOICE_LINE_ID as BIGINT) as invoice_line_id,
    cast(INVOICE_HDR_ID as BIGINT) as invoice_hdr_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(DESCRIPTION as VARCHAR(160)) as description,
    cast(QUANTITY as INTEGER) as quantity,
    cast(UNIT_PRICE as NUMBER(12,2)) as unit_price,
    cast(LINE_AMOUNT as NUMBER(12,2)) as line_amount,
    cast(TAX_AMOUNT as NUMBER(12,2)) as tax_amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(SERVICE_DATE as DATE) as service_date,
    cast(coalesce(INVOICE_ID, INVOICE_HDR_ID) as BIGINT) as invoice_id,
    cast(LINE_NO as INTEGER) as line_no
from {{ source('billing', 'INVOICE_LINE') }}
