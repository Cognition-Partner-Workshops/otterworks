{% set file_format = "CREATE FILE FORMAT IF NOT EXISTS __RUN_DATABASE__.PC_BILLING.BILLING_PSV TYPE=CSV FIELD_DELIMITER='|' SKIP_HEADER=0 FIELD_OPTIONALLY_ENCLOSED_BY=NONE EMPTY_FIELD_AS_NULL=TRUE ESCAPE_UNENCLOSED_FIELD=NONE COMMENT='run_token=__RUN_TOKEN__ expires=2026-11-24'" %}
{{ config(materialized='table', pre_hook=file_format) }}


select
    $1::number(19,0) as INVOICE_ID,
    $2::number(19,0) as CUSTOMER_ID,
    $3::number(19,0) as SUBSCRIPTION_ID,
    to_date($4::varchar, 'YYYY-MM-DD') as INVOICE_DT,
    to_date($5::varchar, 'YYYY-MM-DD') as BILL_DT,
    to_date($6::varchar, 'YYYY-MM-DD') as PERIOD_START_DT,
    coalesce(upper(trim($7)), '{{ var("currency_default", "USD") }}') as CURRENCY_CD,
    round($8::number(38,18), 2)::number(14,2) as TOTAL_AMOUNT,
    upper(trim($9)) as INVOICE_NUMBER,
    $10::number(19,0) as TAX_RATE_ID,
    round($11::number(38,18), 2)::number(14,2) as SUBTOTAL_AMOUNT,
    round($12::number(38,18), 2)::number(14,2) as TAX_AMOUNT,
    trim($13) as INVOICE_PERIOD,
    trunc($14::number(38,18))::integer as PERIOD_KEY,
    to_date($15::varchar, 'YYYY-MM-DD') as PRIOR_PERIOD_END_DT,
    trunc($16::number(38,18))::integer as INVOICE_MONTH,
    trim($17) as PERIOD_CLOSED_CD,
    round($18::number(38,18), 2)::number(14,2) as CURRENCY_CONTROL_TOTAL
from @__RUN_DATABASE__.PC_SRC.LANDING_STAGE/INVOICE_HDR/
    (file_format => '__RUN_DATABASE__.PC_BILLING.BILLING_PSV',
     pattern => '.*{{ var("load_date", "20261109") }}[.]psv')
