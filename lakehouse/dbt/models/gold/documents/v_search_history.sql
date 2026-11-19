select document_id, indexed_ts, status_cd, token_count
from {{ ref('search_index_log') }}
