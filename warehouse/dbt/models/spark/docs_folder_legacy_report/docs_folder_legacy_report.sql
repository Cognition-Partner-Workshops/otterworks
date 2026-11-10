{{ config(materialized='table') }}

select
    f.FOLDER_ID,
    f.FOLDER_NAME,
    f.PARENT_FOLDER_ID,
    count(d.DOCUMENT_ID) as DOCUMENTS
from {{ source('spark_documents', 'FOLDER') }} as f
left join {{ source('spark_documents', 'DOCUMENT') }} as d
    on f.FOLDER_ID = d.FOLDER_ID
group by f.FOLDER_ID, f.FOLDER_NAME, f.PARENT_FOLDER_ID
