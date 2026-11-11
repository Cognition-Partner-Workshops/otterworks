{% set file_format = "CREATE FILE FORMAT IF NOT EXISTS SFX_D1110_AFTER.PC_BILLING.BILLING_PSV TYPE=CSV FIELD_DELIMITER='|' SKIP_HEADER=0 FIELD_OPTIONALLY_ENCLOSED_BY=NONE EMPTY_FIELD_AS_NULL=TRUE ESCAPE_UNENCLOSED_FIELD=NONE COMMENT='run_token=sfx-d1110 expires=2026-11-24'" %}
{{ config(materialized='table', pre_hook=file_format) }}

select
    $1::number(19,0) as CUSTOMER_ID,
    $2::number(19,0) as OWNER_USER_ID,
    left(trim($3), 200)::varchar(200) as ACCOUNT_NAME,
    left(upper(trim($4)), 200)::varchar(200) as STATUS_CD,
    left(coalesce(upper(trim($5)), '{{ var("currency_default", "USD") }}'), 200)::varchar(200) as CURRENCY_CD,
    to_date($6::varchar, 'YYYY-MM-DD') as CREATED_DT,
    left(upper(trim($7)), 200)::varchar(200) as ACCOUNT_NO,
    METADATA$FILE_ROW_NUMBER as SRC_ROW_NO
from @SFX_D1110_AFTER.PC_SRC.LANDING_STAGE/CUSTOMER_ACCOUNT/
    (file_format => 'SFX_D1110_AFTER.PC_BILLING.BILLING_PSV',
     pattern => '.*{{ var("load_date", "20261109") }}[.]psv')
