-- Staging for pkg_document_versions: TRUNCATE stg.stg_document_versions, then load
-- document_versions.csv with Derived Column "DER Normalise timestamps":
--   created_at    = (DT_DBTIMESTAMP2,7) REPLACE(created_at, "+00", "")
--   extracted_at  = @[System::StartTime]  (SQL Server clock, America/New_York)
--   source_system = "document-service"
-- No lookup, split or Script Task; every file row lands. Full reload, no business-date filter.
select
    ID::varchar(36) as id,
    DOCUMENT_ID::varchar(36) as document_id,
    VERSION_NUMBER::int as version_number,
    TITLE::varchar(500) as title,
    CREATED_BY::varchar(36) as created_by,
    replace(CREATED_AT, '+00', '')::timestamp_ntz(7) as created_at,
    nullif(CONTENT_LENGTH, '')::int as content_length,
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz(7) as extracted_at,
    'document-service'::varchar(40) as source_system
from {{ source('pkg_document_versions', 'EXT_DOCUMENT_VERSIONS') }}
