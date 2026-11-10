{% set delete_load = "{% if is_incremental() %}delete from {{ this }} where JOURNAL_NO like 'JE-{{ var(\"load_date\", \"20261109\") }}-%'{% endif %}" %}
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='JOURNAL_LINE_ID', pre_hook=delete_load) }}

with postable as (
    select *,
        round(TOTAL_AMOUNT * {{ var('sales_tax_rate', 0.0825) }}
            / (1 + {{ var('sales_tax_rate', 0.0825) }}), 2)::number(14,2) as TAX_AMOUNT,
        left('JE-{{ var("load_date", "20261109") }}-' || coalesce(INVOICE_NO, ''), 30) as JOURNAL_NO
    from {{ ref('pc_billing__stg_invoice_hdr') }}
    where TOTAL_AMOUNT is not null and TOTAL_AMOUNT <> 0
),
routed as (
    select *, 1 as GROUP_ORDER, '1200' as ACCOUNT_CODE,
        TOTAL_AMOUNT as DEBIT_AMOUNT, 0 as CREDIT_AMOUNT,
        left('Accounts receivable ' || coalesce(INVOICE_NO, ''), 120) as LINE_DESC
    from postable
    union all
    select *, 2 as GROUP_ORDER, '2300' as ACCOUNT_CODE,
        0 as DEBIT_AMOUNT, TOTAL_AMOUNT - TAX_AMOUNT as CREDIT_AMOUNT,
        left('Deferred revenue ' || coalesce(INVOICE_NO, ''), 120) as LINE_DESC
    from postable
    union all
    select *, 3 as GROUP_ORDER, '2200' as ACCOUNT_CODE,
        0 as DEBIT_AMOUNT, TAX_AMOUNT as CREDIT_AMOUNT,
        left('Sales tax payable ' || coalesce(INVOICE_NO, ''), 120) as LINE_DESC
    from postable
    where TAX_AMOUNT <> 0
),
accounts as (
    select rtrim(ACCOUNT_CODE) as ACCOUNT_CODE, GL_ACCOUNT_ID
    from SFX_D1110_AFTER.PC_SRC.GL_ACCOUNT
    qualify row_number() over (partition by ACCOUNT_CODE order by ACCOUNT_CODE) = 1
),
numbered as (
    select r.*, a.GL_ACCOUNT_ID,
        {% if is_incremental() %}
        (select coalesce(max(JOURNAL_LINE_ID), {{ var('gl_seq_start', 900001) }} - 1) from {{ this }})
        {% else %}
        {{ var('gl_seq_start', 900001) }} - 1
        {% endif %}
            + row_number() over (order by r.GROUP_ORDER, r.SRC_ROW_NO) as JOURNAL_LINE_ID
    from routed r
    left join accounts a on r.ACCOUNT_CODE = a.ACCOUNT_CODE
)
select
    JOURNAL_LINE_ID::number(19,0) as JOURNAL_LINE_ID,
    JOURNAL_NO::varchar(30) as JOURNAL_NO,
    INVOICE_ID::number(19,0) as INVOICE_ID,
    GL_ACCOUNT_ID::number(19,0) as GL_ACCOUNT_ID,
    INVOICE_DT::date as POSTING_DT,
    DEBIT_AMOUNT::number(14,2) as DEBIT_AMOUNT,
    CREDIT_AMOUNT::number(14,2) as CREDIT_AMOUNT,
    CURRENCY_CD::varchar(3) as CURRENCY_CD,
    LINE_DESC::varchar(120) as LINE_DESC
from numbered
where CURRENCY_CD is null or length(CURRENCY_CD) <= 3
