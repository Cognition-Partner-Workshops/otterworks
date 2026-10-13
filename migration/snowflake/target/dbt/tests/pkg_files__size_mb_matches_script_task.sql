-- SCR Convert sizes to MB: size_mb = ROUND(size_bytes / 1048576.0, 3) on every row.
select id, size_bytes, size_mb
from {{ ref('stg_files') }}
where size_mb is distinct from round(size_bytes::number(38, 12) / 1048576, 3)
