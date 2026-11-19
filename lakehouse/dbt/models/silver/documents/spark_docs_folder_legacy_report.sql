{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'docs_folder_legacy_report']) }}
select folder_id, folder_name, parent_folder_id, documents
from {{ source('documents_spark_runtime', 'spark_runtime_docs_folder_legacy_report') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
