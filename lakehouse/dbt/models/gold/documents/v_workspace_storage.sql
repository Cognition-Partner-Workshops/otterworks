select owner_user_id, count(*) as document_count, sum(file_size) as total_bytes
from {{ ref('v_document_versions') }}
group by owner_user_id
