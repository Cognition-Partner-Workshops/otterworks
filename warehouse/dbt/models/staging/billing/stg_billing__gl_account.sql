select
    cast(GL_ACCOUNT_ID as BIGINT) as gl_account_id,
    cast(ACCOUNT_CODE as VARCHAR(20)) as account_code,
    cast(ACCOUNT_NAME as VARCHAR(80)) as account_name,
    cast(ACCOUNT_TYPE as VARCHAR(20)) as account_type,
    cast(CURRENCY_CODE as CHAR(3)) as currency_code,
    cast(NORMAL_BALANCE as CHAR(2)) as normal_balance,
    cast(CREATED_AT as TIMESTAMP_NTZ) as created_at,
    cast(IS_ACTIVE as CHAR(1)) as is_active,
    cast(ACCOUNT_NUMBER as VARCHAR(4)) as account_number
from {{ source('billing', 'GL_ACCOUNT') }}
