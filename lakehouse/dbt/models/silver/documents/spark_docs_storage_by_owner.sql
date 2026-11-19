{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'docs_storage_by_owner']) }}
select user_id, email, file_count, size_bytes
from {{ source('documents_spark_runtime', 'spark_runtime_docs_storage_by_owner') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
