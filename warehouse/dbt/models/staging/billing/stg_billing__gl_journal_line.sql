select
    cast(GL_JOURNAL_LINE_ID as BIGINT) as gl_journal_line_id,
    cast(JOURNAL_ID as BIGINT) as journal_id,
    cast(GL_ACCOUNT_ID as BIGINT) as gl_account_id,
    cast(SOURCE_BATCH_NUMBER as VARCHAR(40)) as source_batch_number,
    cast(DESCRIPTION as VARCHAR(160)) as description,
    cast(POSTING_DATE as DATE) as posting_date,
    cast(DEBIT_AMOUNT as NUMBER(12,2)) as debit_amount,
    cast(CREDIT_AMOUNT as NUMBER(12,2)) as credit_amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code
from {{ source('billing', 'GL_JOURNAL_LINE') }}
