-- Staging for pkg_file_versions: file_versions.csv -> stg.stg_file_versions.
-- SQL Truncate stg_file_versions, then DFT Load stg_file_versions reloads the whole file: no
-- filter, lookup or Script Task, and BusinessDate is declared but never read. DER Normalise
-- timestamps deletes the 'T' and 'Z' of created_at and casts to DT_DBTIMESTAMP2(7), adds
-- extracted_at = @[System::StartTime] (server clock, America/New_York) and the constant
-- source_system.
select
    file_id::varchar(36) as file_id,
    version::int as version,
    size_bytes::bigint as size_bytes,
    created_by::varchar(36) as created_by,
    replace(replace(created_at, 'T', ' '), 'Z', '')::timestamp_ntz(7) as created_at,
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz(7) as extracted_at,
    'file-service'::varchar(40) as source_system
from {{ source('pkg_file_versions', 'EXT_FILE_VERSIONS') }}
{%- if var('pkg_file_versions_cut_at_business_date', false) %}
where replace(replace(created_at, 'T', ' '), 'Z', '')::timestamp_ntz(7)
    < dateadd(day, 1, {{ business_date() }})
{%- endif %}
