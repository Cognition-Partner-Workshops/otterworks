{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'docs_folder_tree_walk']) }}
select folder_id, root_folder_id, depth
from {{ source('documents_spark_runtime', 'spark_runtime_docs_folder_tree_walk') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
