-- bytes_used is the peak in MB converted to bytes, exactly as the legacy procedure computes it.
select business_date, tenant_id, peak_storage_mb, bytes_used
from {{ ref('rollup_storage_daily') }}
where bytes_used != peak_storage_mb::number(38, 0) * 1048576
