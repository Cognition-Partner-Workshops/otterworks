{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'docs_share_activity']) }}
select owner_user_id, permission, shares, recipients
from {{ source('documents_spark_runtime', 'spark_runtime_docs_share_activity') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
