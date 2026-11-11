-- Replaces the Spark lake output documents/docs_event_export_hourly
-- (parquet partitioned by EXPORT_BUCKET); the bucket is now a column.
select
    DOCUMENT_ID,
    OWNER_USER_ID,
    FOLDER_ID,
    TITLE,
    CREATED_AT,
    STATUS,
    -- Spark pmod: non-negative remainder for negative ids.
    mod(mod(DOCUMENT_ID, 10000) + 10000, 10000) as EXPORT_BUCKET
from {{ source('spark_documents', 'DOCUMENT') }}
