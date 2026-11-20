{{ config(materialized='incremental', incremental_strategy='merge', unique_key='CUSTOMER_ID') }}

select CUSTOMER_ID, OWNER_USER_ID, ACCOUNT_NAME, STATUS_CD, CURRENCY_CD, CREATED_DT, ACCOUNT_NUMBER, COUNTRY_CD, REGION_CD
from {{ ref('pc_billing__stg_customer_account') }}
where CUSTOMER_ID is not null
    and (ACCOUNT_NAME is null or length(ACCOUNT_NAME) <= 100)
    and (STATUS_CD is null or length(STATUS_CD) <= 12)
    and (CURRENCY_CD is null or length(CURRENCY_CD) <= 3)
    and (ACCOUNT_NUMBER is null or length(ACCOUNT_NUMBER) <= 24)
    and (COUNTRY_CD is null or length(COUNTRY_CD) <= 2)
    and (REGION_CD is null or length(REGION_CD) <= 20)
