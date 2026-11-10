{{ config(alias='DOCS_SEARCH_LOG_PARSE', tags=['sfx-d1110', 'docs_search_log_parse']) }}

select SEARCH_INDEX_LOG_ID, DOCUMENT_ID, EVENT_AT, RAW_LINE, STATUS,
       regexp_substr(coalesce(RAW_LINE, ''), 'action=([[:alnum:]_]+)', 1, 1, 'e', 1) as PARSED_ACTION
from {{ source('spark_documents', 'SEARCH_INDEX_LOG') }}
