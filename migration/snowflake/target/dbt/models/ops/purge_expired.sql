-- Snowflake keeps the run log and facts under the run's retention, so nothing is purged by hand.
select object_name, status
from {{ ref('log_run') }}
qualify row_number() over (partition by object_name order by business_date desc) = 1
