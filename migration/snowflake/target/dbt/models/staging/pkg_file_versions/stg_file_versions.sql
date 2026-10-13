-- Staging for pkg_file_versions: file_versions.csv -> stg.stg_file_versions.
-- The package truncates the table and reloads the whole file each night (no filter, lookup
-- or Script Task); DER Normalise timestamps strips the RFC 3339 'T'/'Z' from created_at and
-- adds extracted_at (package start time) and the constant source_system.
select
    file_id::varchar(36) as file_id,
    version::int as version,
    size_bytes::bigint as size_bytes,
    created_by::varchar(36) as created_by,
    replace(replace(created_at, 'T', ' '), 'Z', '')::timestamp_ntz(7) as created_at,
    current_timestamp()::timestamp_ntz(7) as extracted_at,
    'file-service'::varchar(40) as source_system
from {{ source('pkg_file_versions', 'EXT_FILE_VERSIONS') }}
