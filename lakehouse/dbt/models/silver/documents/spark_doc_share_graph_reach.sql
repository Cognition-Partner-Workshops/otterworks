{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'doc_share_graph_reach']) }}
select user_id, distance
from {{ source('documents_spark_runtime', 'spark_runtime_doc_share_graph_reach') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
