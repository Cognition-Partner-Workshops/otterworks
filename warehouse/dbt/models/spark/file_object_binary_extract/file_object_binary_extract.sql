{{ config(materialized='table', alias='spark__file_object_binary_extract', pre_hook=documents_spark_extract_document()) }}
with extracted as (
 select STORAGE_KEY, DOCS_EXTRACT_DOCUMENT(CONTENT) as X
 from {{ source('spark_documents_binary', 'FILE_OBJECT_BLOBS') }}
)
select f.STORAGE_KEY,f.FILE_OBJECT_ID,f.DOCUMENT_ID,f.SIZE_BYTES,f.CHECKSUM,
       JSON_EXTRACT_PATH_TEXT(TO_JSON(e.X),'MEDIA_TYPE') as MEDIA_TYPE,
       JSON_EXTRACT_PATH_TEXT(TO_JSON(e.X),'TEXT') as TEXT,
       JSON_EXTRACT_PATH_TEXT(TO_JSON(e.X),'PAGE_COUNT')::bigint as PAGE_COUNT,
       JSON_EXTRACT_PATH_TEXT(TO_JSON(e.X),'SHA256') as SHA256,
       JSON_EXTRACT_PATH_TEXT(TO_JSON(e.X),'ERROR') as ERROR,
       '{{ documents_spark_run_date() }}'::varchar as RUN_DATE
from {{ source('spark_documents', 'FILE_OBJECT') }} f
join extracted e on f.STORAGE_KEY=e.STORAGE_KEY
