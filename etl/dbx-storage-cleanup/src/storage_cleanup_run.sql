-- ow_tp_analytics_storage_cleanup / storage_cleanup_run
-- Conversion of etl/scripts/storage_cleanup_daily.py.
--
-- The legacy script listed s3://otterworks-file-storage prefix files/ (paged
-- list_objects_v2), scanned DynamoDB otterworks-file-metadata for s3_key, took
-- orphans = listed keys minus referenced keys, quarantined each via
-- copy_object to s3://otterworks-file-quarantine/quarantined/<ds>/<s3_key>
-- followed by delete_object, then wrote report.json (inventory, orphans,
-- cleanup, savings with S3 $0.023/GB-month) to
-- s3://otterworks-data-lake/reports/storage-cleanup/<ds>/report.json.
--
-- The converted inputs land in the storage_drop UC volume:
--   files_listing_<ds>.jsonl  {s3_key, size_bytes}   (S3 listing snapshot)
--   metadata_keys_<ds>.jsonl  {s3_key}               (DynamoDB scan snapshot)
-- The quarantine copy+delete is preserved as a ledger row per orphan
-- (quarantine_key = the legacy copy destination); source objects are never
-- deleted — the ledger is the auditable action.
--
-- Idempotent: both writes MERGE on their business keys and delete rows absent
-- from the current snapshot — the legacy script rewrote the complete report
-- each run, so the target reflects the current snapshot, not an accumulation.
--
-- Parameters: :ds (run date, 'YYYY-MM-DD').

CREATE OR REPLACE TEMP VIEW cleanup_inventory AS
SELECT s3_key, size_bytes
FROM read_files(
    concat('/Volumes/ow_tp/ow_tp_analytics/storage_drop/files_listing_', :ds, '.jsonl'),
    format => 'json',
    schema => 's3_key STRING, size_bytes BIGINT'
);

CREATE OR REPLACE TEMP VIEW cleanup_referenced AS
SELECT s3_key
FROM read_files(
    concat('/Volumes/ow_tp/ow_tp_analytics/storage_drop/metadata_keys_', :ds, '.jsonl'),
    format => 'json',
    schema => 's3_key STRING'
);

-- Orphans: listed objects the metadata table does not reference (legacy:
-- `referenced` set difference).
CREATE OR REPLACE TEMP VIEW cleanup_orphans AS
SELECT f.s3_key, f.size_bytes
FROM cleanup_inventory f
LEFT ANTI JOIN cleanup_referenced m ON f.s3_key = m.s3_key;

MERGE INTO ow_tp.ow_tp_analytics.storage_quarantine_actions AS tgt
USING (
    SELECT
        s3_key,
        size_bytes,
        concat('s3://otterworks-file-quarantine/quarantined/', :ds, '/', s3_key) AS quarantine_key,
        to_date(:ds) AS quarantined_at
    FROM cleanup_orphans
) AS src
ON tgt.s3_key = src.s3_key
WHEN MATCHED THEN UPDATE SET
    size_bytes = src.size_bytes,
    quarantine_key = src.quarantine_key,
    quarantined_at = src.quarantined_at
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;

MERGE INTO ow_tp.ow_tp_analytics.storage_cleanup_report AS tgt
USING (
    WITH inv AS (
        SELECT COUNT(*) AS total_objects, COALESCE(SUM(size_bytes), 0) AS total_size_bytes
        FROM cleanup_inventory
    ),
    orph AS (
        SELECT COUNT(*) AS orphaned_objects, COALESCE(SUM(size_bytes), 0) AS orphaned_bytes
        FROM cleanup_orphans
    )
    SELECT metric, metric_value, to_date(:ds) AS report_date, current_timestamp() AS generated_at
    FROM (
        SELECT 'report_type' AS metric, 'storage_cleanup' AS metric_value
        UNION ALL SELECT 'report_date', :ds
        UNION ALL SELECT 'generated_at',
               concat(date_format(current_timestamp(), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"), '+00:00')
        UNION ALL SELECT 'inventory.total_objects', CAST((SELECT total_objects FROM inv) AS STRING)
        UNION ALL SELECT 'inventory.total_size_bytes', CAST((SELECT total_size_bytes FROM inv) AS STRING)
        UNION ALL SELECT 'inventory.total_size_gb',
               CAST(ROUND((SELECT total_size_bytes FROM inv) / 1073741824.0, 4) AS STRING)
        UNION ALL SELECT 'orphans.orphaned_objects', CAST((SELECT orphaned_objects FROM orph) AS STRING)
        UNION ALL SELECT 'orphans.orphaned_bytes', CAST((SELECT orphaned_bytes FROM orph) AS STRING)
        -- FLOAT-cast-after-ROUND reproduces legacy str(round(x,4)) formatting:
        -- Spark renders ROUND(x,4) of a zero as '0.0000'; Python prints '0.0'.
        UNION ALL SELECT 'orphans.orphaned_size_gb',
               CAST(CAST(ROUND((SELECT orphaned_bytes FROM orph) / 1073741824.0, 4) AS DOUBLE) AS STRING)
        UNION ALL SELECT 'orphans.orphan_percentage',
               CAST(CAST(ROUND((SELECT orphaned_objects FROM orph) * 100.0
                    / NULLIF((SELECT total_objects FROM inv), 0), 2) AS DOUBLE) AS STRING)
        UNION ALL SELECT 'cleanup.objects_quarantined', CAST((SELECT orphaned_objects FROM orph) AS STRING)
        UNION ALL SELECT 'cleanup.objects_failed', '0'
        UNION ALL SELECT 'cleanup.quarantine_bucket', 'otterworks-file-quarantine'
        UNION ALL SELECT 'savings.storage_freed_gb',
               CAST(CAST(ROUND((SELECT orphaned_bytes FROM orph) / 1073741824.0, 4) AS DOUBLE) AS STRING)
        UNION ALL SELECT 'savings.estimated_monthly_savings_usd',
               CAST(CAST(ROUND((SELECT orphaned_bytes FROM orph) / 1073741824.0 * 0.023, 4) AS DOUBLE) AS STRING)
    ) metrics
) AS src
ON tgt.metric = src.metric
WHEN MATCHED THEN UPDATE SET
    metric_value = src.metric_value,
    report_date = src.report_date,
    generated_at = src.generated_at
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
