select
    cast(GL_JOURNAL_LINE_ID as BIGINT) as gl_journal_line_id,
    cast(JOURNAL_ID as BIGINT) as journal_id,
    cast(GL_ACCOUNT_ID as BIGINT) as gl_account_id,
    cast(SOURCE_BATCH_NUMBER as VARCHAR(40)) as source_batch_number,
    cast(DESCRIPTION as VARCHAR(160)) as description,
    cast(POSTING_DATE as DATE) as posting_date,
    cast(DEBIT_AMOUNT as NUMBER(12,2)) as debit_amount,
    cast(CREDIT_AMOUNT as NUMBER(12,2)) as credit_amount,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(coalesce(JOURNAL_LINE_ID, GL_JOURNAL_LINE_ID) as BIGINT) as journal_line_id,
    cast(INVOICE_ID as BIGINT) as invoice_id,
    cast(CREDIT_NOTE_ID as BIGINT) as credit_note_id,
    cast(POSTING_DT as DATE) as posting_dt,
    cast(CURRENCY_CD as VARCHAR(3)) as currency_cd
from {{ source('billing', 'GL_JOURNAL_LINE') }}
