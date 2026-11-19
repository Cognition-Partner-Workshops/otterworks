{{ config(materialized='ephemeral') }}
select
    cast(version_id as bigint) as version_id,
    cast(document_id as bigint) as document_id,
    cast(version_no as int) as version_no,
    {{ audit_timestamp('version_ts') }} as version_ts,
    cast(file_size as bigint) as file_size,
    {{ legacy_text('content_hash', 64) }} as content_hash
from {{ source('bronze_documents', 'doc_version') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
