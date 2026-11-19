select 
    cast(session_id as bigint) as session_id,
    cast(document_id as bigint) as document_id,
    cast(user_id as bigint) as user_id,
    cast(start_ts as timestamp) as start_ts,
    cast(end_ts as timestamp) as end_ts
from {{ ref('stg_collab_session') }}
