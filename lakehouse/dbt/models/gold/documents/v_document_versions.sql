select d.document_id, d.owner_user_id, v.version_id, v.version_ts, v.file_size
from {{ ref('document') }} d
join {{ ref('doc_version') }} v on d.document_id = v.document_id
