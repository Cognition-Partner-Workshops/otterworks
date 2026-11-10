select
    cast(CUSTOMER_ACCOUNT_ID as BIGINT) as customer_account_id,
    cast(CUSTOMER_ID as BIGINT) as customer_id,
    cast(OWNER_USER_ID as BIGINT) as owner_user_id,
    cast(ACCOUNT_NUMBER as VARCHAR(20)) as account_number,
    cast(LEGAL_NAME as VARCHAR(160)) as legal_name,
    cast(BILLING_COUNTRY as CHAR(2)) as billing_country,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(PAYMENT_TERMS_DAYS as INTEGER) as payment_terms_days,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active
from {{ source('billing', 'CUSTOMER_ACCOUNT') }}
