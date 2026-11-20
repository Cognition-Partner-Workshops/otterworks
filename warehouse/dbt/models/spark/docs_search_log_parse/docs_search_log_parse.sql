{{ config(materialized='table', alias='spark__docs_search_log_parse', pre_hook=documents_spark_parse_action()) }}
select *, DOCS_PARSE_ACTION(RAW_LINE) as PARSED_ACTION
from {{ source('spark_documents', 'SEARCH_INDEX_LOG') }}
