{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'docs_search_log_parse']) }}
select search_index_log_id, document_id, event_at, raw_line, status, parsed_action
from {{ source('documents_spark_runtime', 'spark_runtime_docs_search_log_parse') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
