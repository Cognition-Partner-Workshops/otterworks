{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'docs_tag_normalize']) }}
select doc_tag_id, document_id, tag, normalized_tag
from {{ source('documents_spark_runtime', 'spark_runtime_docs_tag_normalize') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
