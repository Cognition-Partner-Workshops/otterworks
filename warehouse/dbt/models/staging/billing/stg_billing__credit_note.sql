select
    cast(CREDIT_NOTE_ID as BIGINT) as credit_note_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(INVOICE_HDR_ID as BIGINT) as invoice_hdr_id,
    cast(CREDIT_NUMBER as VARCHAR(32)) as credit_number,
    cast(ISSUE_DATE as DATE) as issue_date,
    cast(AMOUNT as NUMBER(12,2)) as amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(REASON as VARCHAR(120)) as reason,
    cast(STATUS as VARCHAR(20)) as status,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(coalesce(INVOICE_ID, INVOICE_HDR_ID) as BIGINT) as invoice_id,
    cast(CREDIT_DT as DATE) as credit_dt,
    cast(REASON_CD as VARCHAR(12)) as reason_cd,
    cast(REASON_TEXT as VARCHAR(120)) as reason_text
from {{ source('billing', 'CREDIT_NOTE') }}
