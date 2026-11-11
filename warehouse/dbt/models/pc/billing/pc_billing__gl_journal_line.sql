{% set prior_keys = "{% if is_incremental() %}create or replace temporary table {{ this.database }}.{{ this.schema }}.GL_JOURNAL_LINE_PRIOR_KEYS comment='run_token=sfx-d1110 expires=2026-11-24' as select JOURNAL_NO, GL_ACCOUNT_ID, JOURNAL_LINE_ID, row_number() over (partition by JOURNAL_NO, GL_ACCOUNT_ID order by JOURNAL_LINE_ID) as OCCURRENCE from {{ this }} where JOURNAL_NO like 'JE-{{ var(\"load_date\", \"20261109\") }}-%'{% endif %}" %}
{% set delete_load = "{% if is_incremental() %}delete from {{ this }} where JOURNAL_NO like 'JE-{{ var(\"load_date\", \"20261109\") }}-%'{% endif %}" %}
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='JOURNAL_LINE_ID', pre_hook=[prior_keys, delete_load]) }}

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
keyed as (
    select r.*, a.GL_ACCOUNT_ID,
        row_number() over (partition by r.JOURNAL_NO, a.GL_ACCOUNT_ID order by r.GROUP_ORDER, r.SRC_ROW_NO) as OCCURRENCE
    from routed r
    left join accounts a on r.ACCOUNT_CODE = a.ACCOUNT_CODE
),
{% if is_incremental() %}
{% set prior = this.database ~ '.' ~ this.schema ~ '.GL_JOURNAL_LINE_PRIOR_KEYS' %}
reused as (
    select k.*, p.JOURNAL_LINE_ID as PRIOR_ID
    from keyed k
    left join {{ prior }} p
        on p.JOURNAL_NO = k.JOURNAL_NO and equal_null(p.GL_ACCOUNT_ID, k.GL_ACCOUNT_ID)
        and p.OCCURRENCE = k.OCCURRENCE
),
numbered as (
    select *,
        coalesce(PRIOR_ID, greatest(
            (select coalesce(max(JOURNAL_LINE_ID), {{ var('gl_seq_start', 900001) }} - 1) from {{ this }}),
            (select coalesce(max(JOURNAL_LINE_ID), {{ var('gl_seq_start', 900001) }} - 1) from {{ prior }}))
            + row_number() over (partition by PRIOR_ID is null order by GROUP_ORDER, SRC_ROW_NO)) as JOURNAL_LINE_ID
    from reused
)
{% else %}
numbered as (
    select *,
        {{ var('gl_seq_start', 900001) }} - 1
            + row_number() over (order by GROUP_ORDER, SRC_ROW_NO) as JOURNAL_LINE_ID
    from keyed
)
{% endif %}
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
