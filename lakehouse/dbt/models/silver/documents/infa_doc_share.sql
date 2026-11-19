select * from {{ source('documents_informatica_runtime', 'infa_runtime_doc_share') }}
