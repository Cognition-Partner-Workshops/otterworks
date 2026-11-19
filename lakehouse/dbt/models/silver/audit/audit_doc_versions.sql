{{ config(materialized='ephemeral') }}
select version_id, document_id, version_no, version_ts, file_size, content_hash
from (select *, row_number() over (partition by document_id order by version_ts desc) as rn
      from {{ ref('audit_input_doc_version') }}) v where rn=1
