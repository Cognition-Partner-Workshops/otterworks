select * from {{ source('raw_doc_search_api', 'DOCUMENT_DOCUMENTS') }}
where _export_id is not null
qualify row_number() over (
 partition by _export_id, id
 order by _loaded_at desc, _file_name desc, _file_row_number desc
) = 1
