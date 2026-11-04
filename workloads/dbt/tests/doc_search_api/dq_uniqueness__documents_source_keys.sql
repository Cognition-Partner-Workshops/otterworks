{{ config(tags=['dq', 'dq_doc_search_api', 'dq_uniqueness']) }}

select _file_name, id, count(*) as key_count
from {{ source('raw_doc_search_api', 'DOCUMENT_DOCUMENTS') }}
group by 1, 2 having count(*) > 1
