select
    cast(gl_account_id as bigint) as gl_account_id,
    {{ legacy_text('account_number', 4, true) }} as account_number,
    {{ legacy_text('account_name', 80) }} as account_name,
    {{ legacy_text('account_type', 12, true) }} as account_type,
    {{ legacy_text('normal_balance', 2, true) }} as normal_balance
from {{ ref('stg_gl_account') }}
