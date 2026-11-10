select
    cast(BILLING_ADJ_ID as BIGINT) as billing_adj_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(INVOICE_HDR_ID as BIGINT) as invoice_hdr_id,
    cast(ADJUSTMENT_DATE as DATE) as adjustment_date,
    cast(AMOUNT as NUMBER(12,2)) as amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(REASON as VARCHAR(120)) as reason,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active,
    cast(coalesce(ADJUSTMENT_ID, BILLING_ADJ_ID) as BIGINT) as adjustment_id,
    cast(coalesce(INVOICE_ID, INVOICE_HDR_ID) as BIGINT) as invoice_id,
    cast(ADJUSTMENT_DT as DATE) as adjustment_dt,
    cast(REASON_CD as VARCHAR(12)) as reason_cd
from {{ source('billing', 'BILLING_ADJ') }}
