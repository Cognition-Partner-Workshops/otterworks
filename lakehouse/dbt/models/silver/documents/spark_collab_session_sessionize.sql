{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'collab_session_sessionize']) }}
select user_id, document_id, session_number, start_at, end_at
from {{ source('documents_spark_runtime', 'spark_runtime_collab_session_sessionize') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
