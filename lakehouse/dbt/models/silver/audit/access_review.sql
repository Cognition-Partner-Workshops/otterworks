select
    cast(review_id as bigint) as review_id,
    cast(user_id as bigint) as user_id,
    cast(document_id as bigint) as document_id,
    cast(review_dt as date) as review_dt,
    {{ legacy_text('decision_cd', 12, true) }} as decision_cd
from {{ source('bronze_audit', 'access_review') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
