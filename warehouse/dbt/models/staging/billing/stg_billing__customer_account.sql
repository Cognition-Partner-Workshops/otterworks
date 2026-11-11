select
    cast(CUSTOMER_ACCOUNT_ID as BIGINT) as customer_account_id,
    cast(coalesce(CUSTOMER_ID, CUSTOMER_ACCOUNT_ID) as BIGINT) as customer_id,
    cast(OWNER_USER_ID as BIGINT) as owner_user_id,
    cast(ACCOUNT_NUMBER as VARCHAR(24)) as account_number,
    cast(LEGAL_NAME as VARCHAR(160)) as legal_name,
    cast(BILLING_COUNTRY as CHAR(2)) as billing_country,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(PAYMENT_TERMS_DAYS as INTEGER) as payment_terms_days,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active,
    cast(ACCOUNT_NAME as VARCHAR(100)) as account_name,
    cast(STATUS_CD as VARCHAR(12)) as status_cd,
    cast(CURRENCY_CD as VARCHAR(3)) as currency_cd,
    cast(CREATED_DT as DATE) as created_dt,
    cast(COUNTRY_CD as VARCHAR(2)) as country_cd,
    cast(REGION_CD as VARCHAR(20)) as region_cd
from {{ source('billing', 'CUSTOMER_ACCOUNT') }}
