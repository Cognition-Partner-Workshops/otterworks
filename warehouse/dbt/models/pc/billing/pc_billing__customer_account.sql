{{ config(materialized='incremental', incremental_strategy='merge', unique_key='CUSTOMER_ID') }}

select
    CUSTOMER_ID::number(19,0) as CUSTOMER_ID,
    OWNER_USER_ID::number(19,0) as OWNER_USER_ID,
    ACCOUNT_NAME::varchar(100) as ACCOUNT_NAME,
    STATUS_CD::varchar(12) as STATUS_CD,
    CURRENCY_CD::varchar(3) as CURRENCY_CD,
    CREATED_DT::date as CREATED_DT,
    ACCOUNT_NO::varchar(20) as ACCOUNT_NO
from {{ ref('pc_billing__stg_customer_account') }}
where CUSTOMER_ID is not null
    and (ACCOUNT_NAME is null or length(ACCOUNT_NAME) <= 100)
    and (STATUS_CD is null or length(STATUS_CD) <= 12)
    and (CURRENCY_CD is null or length(CURRENCY_CD) <= 3)
    and (ACCOUNT_NO is null or length(ACCOUNT_NO) <= 20)
qualify row_number() over (partition by CUSTOMER_ID order by SRC_ROW_NO) = 1
