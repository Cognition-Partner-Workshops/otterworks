{{ config(materialized='ephemeral') }}
select
    cast(share_id as bigint) as share_id,
    cast(document_id as bigint) as document_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('access_level', 12, true) }} as access_level,
    cast(shared_dt as date) as shared_dt
from {{ source('bronze_documents', 'doc_share') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
