{{ config(materialized='table', alias='spark__docs_folder_legacy_report') }}
select f.FOLDER_ID, f.FOLDER_NAME, f.PARENT_FOLDER_ID, count(d.DOCUMENT_ID) as DOCUMENTS
from {{ source('spark_documents', 'FOLDER') }} f
left join {{ source('spark_documents', 'DOCUMENT') }} d on f.FOLDER_ID=d.FOLDER_ID
group by f.FOLDER_ID,f.FOLDER_NAME,f.PARENT_FOLDER_ID
