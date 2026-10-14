-- pkg_audit's tenant lookup never drops or duplicates an event: one staging row per extract row.
select extract_rows, staging_rows
from (
    select
        (select count(*) from {{ source('pkg_audit', 'EXT_AUDIT_EVENTS') }}) as extract_rows,
        (select count(*) from {{ ref('stg_audit_events') }}) as staging_rows
)
where extract_rows <> staging_rows
