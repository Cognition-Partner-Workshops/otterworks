-- ow_tp_analytics_usage_rollup / rollup_load
-- Converted UsageRollupJob + UsageRollupAggregator + EventLoader.
--
-- The legacy job read seed/usage-events.ndjson via ROLLUP_INPUT, grouped
-- events by UTC calendar day (Instant.atZone(UTC).toLocalDate), and emitted
-- one DailyUsageRollup per day: total_events = every event, active_users =
-- distinct userId, per-type counters, and storage bytes summed from
-- metadata["bytes"] with a parse-failure fallback of 0. The converted input
-- is the UC volume /Volumes/ow_tp/ow_tp_analytics/rollup_input/*.ndjson.
--
-- EventLoader skips blank and '#'-prefixed lines; read_files' permissive
-- mode lands them as rescued rows, so the WHERE clause drops them the same
-- way. The legacy instantFormat also accepts JSON numbers as epoch
-- milliseconds, so numeric timestamps go through timestamp_millis. The UTC
-- calendar day comes from unix-seconds/86400 -> date_from_unix_date, which
-- never depends on the warehouse session timezone.
--
-- Idempotent snapshot load: MERGE on date, and days absent from the current
-- input are deleted — the legacy job rewrote the complete report each run,
-- so the target reflects the current snapshot, not an accumulation.

MERGE INTO ow_tp.ow_tp_analytics.usage_rollup AS tgt
USING (
    SELECT
        DATE_FROM_UNIX_DATE(CAST(FLOOR(unix_timestamp(instant) / 86400) AS INT)) AS date,
        COUNT(DISTINCT userId) AS active_users,
        COUNT(*) FILTER (WHERE eventType = 'collab.session_started') AS collab_sessions,
        COUNT(*) FILTER (WHERE eventType = 'document.created') AS documents_created,
        COUNT(*) FILTER (WHERE eventType = 'document.edited') AS documents_edited,
        COUNT(*) FILTER (WHERE eventType = 'document.viewed') AS documents_viewed,
        COUNT(*) FILTER (WHERE eventType = 'file.downloaded') AS files_downloaded,
        COUNT(*) FILTER (WHERE eventType = 'file.uploaded') AS files_uploaded,
        COALESCE(SUM(COALESCE(try_cast(metadata['bytes'] AS BIGINT), 0))
            FILTER (WHERE eventType = 'storage.allocated'), 0)
        - COALESCE(SUM(COALESCE(try_cast(metadata['bytes'] AS BIGINT), 0))
            FILTER (WHERE eventType = 'storage.released'), 0) AS net_storage_bytes,
        COALESCE(SUM(COALESCE(try_cast(metadata['bytes'] AS BIGINT), 0))
            FILTER (WHERE eventType = 'storage.allocated'), 0) AS storage_allocated_bytes,
        COALESCE(SUM(COALESCE(try_cast(metadata['bytes'] AS BIGINT), 0))
            FILTER (WHERE eventType = 'storage.released'), 0) AS storage_released_bytes,
        COUNT(*) AS total_events,
        CURRENT_TIMESTAMP() AS generated_at,
        COUNT(*) OVER () AS day_count
    FROM (
        SELECT
            *,
            CASE
                WHEN timestamp RLIKE '^-?[0-9]+$'
                    THEN timestamp_millis(CAST(timestamp AS BIGINT))
                ELSE to_timestamp(timestamp)
            END AS instant
        FROM read_files(
            '/Volumes/ow_tp/ow_tp_analytics/rollup_input/*.ndjson',
            format => 'json',
            schema => 'eventId STRING, eventType STRING, metadata MAP<STRING,STRING>, resourceId STRING, resourceType STRING, timestamp STRING, userId STRING'
        )
    )
    WHERE eventType IS NOT NULL AND timestamp IS NOT NULL AND instant IS NOT NULL
    GROUP BY DATE_FROM_UNIX_DATE(CAST(FLOOR(unix_timestamp(instant) / 86400) AS INT))
) AS src
ON tgt.date = src.date
WHEN MATCHED THEN UPDATE SET
    active_users = src.active_users,
    collab_sessions = src.collab_sessions,
    documents_created = src.documents_created,
    documents_edited = src.documents_edited,
    documents_viewed = src.documents_viewed,
    files_downloaded = src.files_downloaded,
    files_uploaded = src.files_uploaded,
    net_storage_bytes = src.net_storage_bytes,
    storage_allocated_bytes = src.storage_allocated_bytes,
    storage_released_bytes = src.storage_released_bytes,
    total_events = src.total_events,
    generated_at = src.generated_at,
    day_count = src.day_count
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
