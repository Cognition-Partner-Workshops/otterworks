{% set file_format = "CREATE FILE FORMAT IF NOT EXISTS SFX_D1110_AFTER.PC_BILLING.BILLING_PSV TYPE=CSV FIELD_DELIMITER='|' SKIP_HEADER=0 FIELD_OPTIONALLY_ENCLOSED_BY=NONE EMPTY_FIELD_AS_NULL=TRUE ESCAPE_UNENCLOSED_FIELD=NONE COMMENT='run_token=sfx-d1110 expires=2026-11-24'" %}
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='PAYMENT_ID', pre_hook=file_format) }}

with expressions as (
    select
        $1::number(19,0) as PAYMENT_ID,
        $2::number(19,0) as INVOICE_ID,
        $3::number(19,0) as CUSTOMER_ID,
        to_date($4::varchar, 'YYYY-MM-DD') as PAYMENT_DT,
        round($5::number(38,18), 2)::number(14,2) as AMOUNT,
        left(upper(trim($6)), 12)::varchar(12) as METHOD_CD,
        METADATA$FILE_ROW_NUMBER as SRC_ROW_NO
    from @SFX_D1110_AFTER.PC_SRC.LANDING_STAGE/PAYMENT/
    (file_format => 'SFX_D1110_AFTER.PC_BILLING.BILLING_PSV',
     pattern => '.*{{ var("load_date", "20261109") }}[.]psv')
)
select *
from expressions
where PAYMENT_ID is not null and AMOUNT is not null
qualify row_number() over (partition by PAYMENT_ID order by SRC_ROW_NO desc) = 1
