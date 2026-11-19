{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'doc_version_diff_stats']) }}
select doc_version_id, document_id, version_number, body, created_at, previous_body, similarity
from {{ source('documents_spark_runtime', 'spark_runtime_doc_version_diff_stats') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
