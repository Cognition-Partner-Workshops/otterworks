{% set file_format = "CREATE FILE FORMAT IF NOT EXISTS __RUN_DATABASE__.PC_BILLING.BILLING_PSV TYPE=CSV FIELD_DELIMITER='|' SKIP_HEADER=0 FIELD_OPTIONALLY_ENCLOSED_BY=NONE EMPTY_FIELD_AS_NULL=TRUE ESCAPE_UNENCLOSED_FIELD=NONE COMMENT='run_token=__RUN_TOKEN__ expires=2026-11-24'" %}
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='INVOICE_LINE_ID', pre_hook=file_format) }}

with expressions as (
    select
        $1::number(19,0) as INVOICE_LINE_ID,
        $2::number(19,0) as INVOICE_ID,
        trunc($3::number(38,18))::integer as LINE_NO,
        left(trim($4), 120)::varchar(120) as DESCRIPTION,
        trunc($5::number(38,18))::integer as QUANTITY,
        round($6::number(38,18), 2)::number(14,2) as UNIT_PRICE,
        coalesce(round($7::number(38,18), 2),
            round(trunc($5::number(38,18)) * round($6::number(38,18), 2), 2))::number(14,2) as LINE_AMOUNT,
        METADATA$FILE_ROW_NUMBER as SRC_ROW_NO
    from @__RUN_DATABASE__.PC_SRC.LANDING_STAGE/INVOICE_LINE/
    (file_format => '__RUN_DATABASE__.PC_BILLING.BILLING_PSV',
     pattern => '.*{{ var("load_date", "20261109") }}[.]psv')
)
select *
from expressions
where INVOICE_ID is not null and INVOICE_LINE_ID is not null
qualify row_number() over (partition by INVOICE_LINE_ID order by SRC_ROW_NO desc) = 1
