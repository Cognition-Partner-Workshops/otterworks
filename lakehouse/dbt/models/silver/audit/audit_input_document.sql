{{ config(materialized='ephemeral') }}
select
    cast(document_id as bigint) as document_id,
    cast(folder_id as bigint) as folder_id,
    cast(owner_user_id as bigint) as owner_user_id,
    cast(customer_id as bigint) as customer_id,
    {{ legacy_text('document_name', 120) }} as document_name,
    cast(created_dt as date) as created_dt,
    {{ legacy_text('status_cd', 12, true) }} as status_cd,
    {{ legacy_text('file_type', 8, true) }} as file_type
from {{ source('bronze_documents', 'document') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
