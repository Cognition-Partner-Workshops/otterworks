{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'lake_compaction_documents']) }}
select document_id, owner_user_id, folder_id, title, created_at, status, export_bucket
from {{ source('documents_spark_runtime', 'spark_runtime_lake_compaction_documents') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
