{{ config(materialized='ephemeral') }}
select
    cast(tag_id as bigint) as tag_id,
    cast(document_id as bigint) as document_id,
    {{ legacy_text('tag_name', 40) }} as tag_name,
    cast(created_dt as date) as created_dt
from {{ source('bronze_documents', 'doc_tag') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
