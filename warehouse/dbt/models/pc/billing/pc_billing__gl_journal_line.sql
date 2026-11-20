{% set prior_keys = "{% if is_incremental() %}create or replace temporary table {{ this.database }}.{{ this.schema }}.GL_JOURNAL_LINE_PRIOR_KEYS comment='run_token=__RUN_TOKEN__ expires=2026-11-24' as select INVOICE_ID, GL_ACCOUNT_ID, JOURNAL_LINE_ID, row_number() over (partition by INVOICE_ID, GL_ACCOUNT_ID order by JOURNAL_LINE_ID) as OCCURRENCE from {{ this }} where CREDIT_NOTE_ID is null{% endif %}" %}
{% set delete_load = "{% if is_incremental() %}delete from {{ this }} where CREDIT_NOTE_ID is null and INVOICE_ID in (select INVOICE_ID from {{ ref('pc_billing__stg_invoice_hdr') }} where TOTAL_AMOUNT is not null and TOTAL_AMOUNT <> 0){% endif %}" %}
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='JOURNAL_LINE_ID', pre_hook=[prior_keys, delete_load]) }}

with postable as (
    select *,
        coalesce(TAX_AMOUNT, round(TOTAL_AMOUNT * {{ var('sales_tax_rate', 0.0825) }}
            / (1 + {{ var('sales_tax_rate', 0.0825) }}), 2))::number(14,2) as POSTING_TAX
    from {{ ref('pc_billing__stg_invoice_hdr') }}
    where TOTAL_AMOUNT is not null and TOTAL_AMOUNT <> 0
),
routed as (
    select *, 1 as GROUP_ORDER, '1200' as ACCOUNT_NUMBER,
        TOTAL_AMOUNT as DEBIT_AMOUNT, 0 as CREDIT_AMOUNT,
        left('Accounts receivable ' || coalesce(INVOICE_NUMBER, ''), 120) as DESCRIPTION
    from postable
    union all
    select *, 2 as GROUP_ORDER, '2300' as ACCOUNT_NUMBER,
        0 as DEBIT_AMOUNT, TOTAL_AMOUNT - POSTING_TAX as CREDIT_AMOUNT,
        left('Deferred revenue ' || coalesce(INVOICE_NUMBER, ''), 120) as DESCRIPTION
    from postable
    union all
    select *, 3 as GROUP_ORDER, '2200' as ACCOUNT_NUMBER,
        0 as DEBIT_AMOUNT, POSTING_TAX as CREDIT_AMOUNT,
        left('Sales tax payable ' || coalesce(INVOICE_NUMBER, ''), 120) as DESCRIPTION
    from postable
    where POSTING_TAX <> 0
),
accounts as (
    select rtrim(ACCOUNT_NUMBER) as ACCOUNT_NUMBER, GL_ACCOUNT_ID
    from __RUN_DATABASE__.PC_SRC.GL_ACCOUNT
    qualify row_number() over (partition by ACCOUNT_NUMBER order by ACCOUNT_NUMBER) = 1
),
keyed as (
    select r.*, a.GL_ACCOUNT_ID,
        row_number() over (partition by r.INVOICE_ID, a.GL_ACCOUNT_ID order by r.GROUP_ORDER) as OCCURRENCE
    from routed r
    left join accounts a on r.ACCOUNT_NUMBER = a.ACCOUNT_NUMBER
),
{% if is_incremental() %}
reused as (
    select k.*, p.JOURNAL_LINE_ID as PRIOR_ID
    from keyed k
    left join {{ this.database }}.{{ this.schema }}.GL_JOURNAL_LINE_PRIOR_KEYS p
        on p.INVOICE_ID = k.INVOICE_ID and equal_null(p.GL_ACCOUNT_ID, k.GL_ACCOUNT_ID)
        and p.OCCURRENCE = k.OCCURRENCE
),
numbered as (
    select *, coalesce(PRIOR_ID, greatest(
        (select coalesce(max(JOURNAL_LINE_ID), {{ var('gl_seq_start', 8000000000001) }} - 1) from {{ this }}),
        (select coalesce(max(JOURNAL_LINE_ID), {{ var('gl_seq_start', 8000000000001) }} - 1)
            from {{ this.database }}.{{ this.schema }}.GL_JOURNAL_LINE_PRIOR_KEYS))
        + row_number() over (partition by PRIOR_ID is null order by GROUP_ORDER, INVOICE_ID)) as JOURNAL_LINE_ID
    from reused
)
{% else %}
numbered as (
    select *, {{ var('gl_seq_start', 8000000000001) }} - 1
        + row_number() over (order by GROUP_ORDER, INVOICE_ID) as JOURNAL_LINE_ID
    from keyed
)
{% endif %}
select
    r.JOURNAL_LINE_ID::number(19,0) as JOURNAL_LINE_ID,
    r.INVOICE_ID::number(19,0) as INVOICE_ID,
    null::number(19,0) as CREDIT_NOTE_ID,
    r.GL_ACCOUNT_ID::number(19,0) as GL_ACCOUNT_ID,
    r.INVOICE_DT::date as POSTING_DT,
    upper(trim(r.CURRENCY_CD))::varchar(3) as CURRENCY_CD,
    r.DEBIT_AMOUNT::number(14,2) as DEBIT_AMOUNT,
    r.CREDIT_AMOUNT::number(14,2) as CREDIT_AMOUNT,
    r.DESCRIPTION::varchar(120) as DESCRIPTION
from numbered r
where r.CURRENCY_CD is null or length(trim(r.CURRENCY_CD)) <= 3
