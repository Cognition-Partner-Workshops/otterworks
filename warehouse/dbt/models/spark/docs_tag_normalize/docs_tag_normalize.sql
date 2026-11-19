{{ config(materialized='table', alias='spark__docs_tag_normalize', pre_hook=documents_spark_normalize()) }}
select *, DOCS_NORMALIZE(TAG) as NORMALIZED_TAG
from {{ source('spark_documents', 'DOC_TAG') }}
