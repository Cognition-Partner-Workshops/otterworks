{% set file_format = "CREATE FILE FORMAT IF NOT EXISTS SFX_D1110_AFTER.PC_BILLING.BILLING_PSV TYPE=CSV FIELD_DELIMITER='|' SKIP_HEADER=0 FIELD_OPTIONALLY_ENCLOSED_BY=NONE EMPTY_FIELD_AS_NULL=TRUE ESCAPE_UNENCLOSED_FIELD=NONE COMMENT='run_token=sfx-d1110 expires=2026-11-24'" %}
{{ config(materialized='table', pre_hook=file_format) }}

select
    $1::number(19,0) as INVOICE_ID,
    $2::number(19,0) as CUSTOMER_ID,
    $3::number(19,0) as SUBSCRIPTION_ID,
    to_date($4::varchar, 'YYYY-MM-DD') as INVOICE_DT,
    to_date($5::varchar, 'YYYY-MM-DD') as BILL_DT,
    to_date($6::varchar, 'YYYY-MM-DD') as PERIOD_START_DT,
    left(coalesce(upper(trim($7)), '{{ var("currency_default", "USD") }}'), 200)::varchar(200) as CURRENCY_CD,
    round($8::number(38,18), 2)::number(14,2) as TOTAL_AMOUNT,
    left(upper(trim($9)), 200)::varchar(200) as INVOICE_NO,
    METADATA$FILE_ROW_NUMBER as SRC_ROW_NO
from @SFX_D1110_AFTER.PC_SRC.LANDING_STAGE/INVOICE_HDR/
    (file_format => 'SFX_D1110_AFTER.PC_BILLING.BILLING_PSV',
     pattern => '.*{{ var("load_date", "20261109") }}[.]psv')
