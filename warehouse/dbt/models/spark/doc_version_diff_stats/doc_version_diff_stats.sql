{{ config(materialized='table', alias='spark__doc_version_diff_stats', pre_hook=documents_spark_similarity()) }}
with versions as (
 select *, lag(BODY) over (partition by DOCUMENT_ID order by VERSION_NUMBER) as PREVIOUS_BODY
 from {{ source('spark_documents', 'DOC_VERSION') }}
)
select DOC_VERSION_ID,DOCUMENT_ID,VERSION_NUMBER,BODY,CREATED_AT,PREVIOUS_BODY,
       DOCS_SIMILARITY(PREVIOUS_BODY,BODY) as SIMILARITY from versions
