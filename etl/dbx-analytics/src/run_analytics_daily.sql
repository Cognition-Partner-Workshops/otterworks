-- ow_tp_analytics_daily / run_analytics_daily
-- Conversion of etl/scripts/analytics_daily.py (SQS otterworks-analytics +
-- DynamoDB otterworks-analytics-events -> Postgres analytics_daily_summary +
-- S3 otterworks-data-lake report) to Lakeflow SQL.
--
-- The legacy extract (SQS drain + `begins_with(event_date, :ds)` DynamoDB
-- scan) is carried by tools/analytics_extract.py, which lands the day's events
-- as `analytics_events_<ds>.jsonl` in the analytics_drop volume: SQS-sourced
-- events carry source='sqs' and are all consumed (the legacy drain had no date
-- filter); DynamoDB-sourced events carry source='dynamodb' + event_date and
-- keep the begins_with filter here.
--
-- Idempotent: both writes MERGE on their business keys. A rerun re-reads every
-- snapshot file for the run date and converges to the same rows; files may be
-- re-dropped harmlessly.
--
-- Parameters: :ds (run date, 'YYYY-MM-DD').

CREATE OR REPLACE TEMP VIEW analytics_events AS
SELECT
    -- event_type/eventType normalization (legacy: event_type promoted when
    -- eventType absent, else 'unknown')
    -- legacy promotes event_type -> eventType as a column only when the whole
    -- batch lacks eventType; a mixed batch keeps event_type rows unpromoted
    -- (NaN), which lands them in total_events but outside every typed bucket.
    COALESCE(
        CASE
            WHEN MAX(CASE WHEN eventType IS NOT NULL THEN 1 ELSE 0 END) OVER () = 1
                THEN eventType
            ELSE event_type
        END,
        'unknown'
    ) AS event_type,
    -- resolved_user_id priority ownerId > editedBy > authorId > deletedBy >
    -- userId, blank/empty fields skipped, 'unknown' fallback
    COALESCE(
        NULLIF(ownerId, ''), NULLIF(editedBy, ''), NULLIF(authorId, ''),
        NULLIF(deletedBy, ''), NULLIF(userId, ''), 'unknown'
    ) AS resolved_user_id,
    -- hour bucket from the ISO timestamp; unparseable -> '00'
    CASE
        WHEN try_to_timestamp(timestamp) IS NOT NULL
            THEN printf('%02d', hour(try_to_timestamp(timestamp)))
        ELSE '00'
    END AS hour,
    documentId,
    fileId,
    sizeBytes
FROM read_files(
    concat('/Volumes/ow_tp/ow_tp_analytics/analytics_drop/analytics_events_', :ds, '*.jsonl'),
    format => 'json',
    schema => concat(
        'source STRING, event_id STRING, event_date STRING, eventType STRING, ',
        'event_type STRING, timestamp STRING, documentId STRING, fileId STRING, ',
        'sizeBytes BIGINT, ownerId STRING, editedBy STRING, authorId STRING, ',
        'deletedBy STRING, userId STRING'
    )
)
WHERE source = 'sqs' OR event_date LIKE concat(:ds, '%');

-- Artifact rows land in analytics_daily_report keyed by their legacy S3 path.
-- partition_key = reports/analytics/daily/year=<y>/month=<m>/day=<d>/
CREATE OR REPLACE TEMP VIEW analytics_artifacts AS
SELECT
    concat(
        'reports/analytics/daily/year=', substr(:ds, 1, 4),
        '/month=', substr(:ds, 6, 2), '/day=', substr(:ds, 9, 2),
        '/', artifact_name
    ) AS s3_key,
    artifact_type
FROM (
    VALUES
        ('top_users.jsonl.gz', 'analytics_top_users'),
        ('hourly_breakdown.json.gz', 'analytics_hourly_breakdown')
) AS t(artifact_name, artifact_type);

-- Daily summary row (Postgres analytics_daily_summary upsert equivalent).
MERGE INTO ow_tp.ow_tp_analytics.analytics_daily_summary AS tgt
USING (
    SELECT
        CAST(:ds AS DATE) AS report_date,
        COUNT(DISTINCT CASE WHEN resolved_user_id <> 'unknown'
                            THEN resolved_user_id END) AS active_users,
        COUNT(DISTINCT CASE WHEN event_type IN ('document_created', 'document_edited')
                            THEN documentId END) AS active_documents,
        COUNT(DISTINCT CASE WHEN event_type IN ('file_uploaded', 'file_shared', 'file_deleted')
                            THEN fileId END) AS active_files,
        COUNT(*) AS total_events,
        COUNT_IF(event_type = 'document_created') AS documents_created,
        COUNT_IF(event_type = 'document_edited') AS documents_edited,
        COUNT_IF(event_type = 'comment_added') AS comments_added,
        COUNT_IF(event_type = 'file_uploaded') AS files_uploaded,
        COUNT_IF(event_type = 'file_shared') AS files_shared,
        COUNT_IF(event_type = 'file_deleted') AS files_deleted,
        COALESCE(SUM(CASE WHEN event_type = 'file_uploaded'
                          THEN sizeBytes END), 0) AS bytes_uploaded,
        CURRENT_TIMESTAMP() AS updated_at
    FROM analytics_events
    -- legacy writes nothing when the day produced no events
    HAVING COUNT(*) > 0
) AS src
ON tgt.report_date = src.report_date
WHEN MATCHED THEN UPDATE SET
    active_users = src.active_users,
    active_documents = src.active_documents,
    active_files = src.active_files,
    total_events = src.total_events,
    documents_created = src.documents_created,
    documents_edited = src.documents_edited,
    comments_added = src.comments_added,
    files_uploaded = src.files_uploaded,
    files_shared = src.files_shared,
    files_deleted = src.files_deleted,
    bytes_uploaded = src.bytes_uploaded,
    updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    report_date, active_users, active_documents, active_files,
    total_events, documents_created, documents_edited, comments_added,
    files_uploaded, files_shared, files_deleted, bytes_uploaded, updated_at
) VALUES (
    src.report_date, src.active_users, src.active_documents, src.active_files,
    src.total_events, src.documents_created, src.documents_edited,
    src.comments_added, src.files_uploaded, src.files_shared,
    src.files_deleted, src.bytes_uploaded, src.updated_at
);

-- Daily report row (S3 reports/analytics/daily/<ds>/report.json equivalent):
-- summary + highlights (peak hour, top-5 users) + document/file metrics.
MERGE INTO ow_tp.ow_tp_analytics.analytics_daily_report AS tgt
USING (
    SELECT
        concat('reports/analytics/daily/', :ds, '/report.json') AS s3_key,
        'daily_analytics' AS report_type,
        CAST(:ds AS DATE) AS report_date,
        CURRENT_TIMESTAMP() AS generated_at,
        to_json(named_struct(
            'report_type', 'daily_analytics',
            'report_date', :ds,
            'generated_at', CAST(CURRENT_TIMESTAMP() AS STRING),
            'summary', named_struct(
                'active_users', s.active_users,
                'active_documents', s.active_documents,
                'active_files', s.active_files,
                'total_events', s.total_events,
                'documents_created', s.documents_created,
                'documents_edited', s.documents_edited,
                'comments_added', s.comments_added,
                'files_uploaded', s.files_uploaded,
                'files_shared', s.files_shared,
                'files_deleted', s.files_deleted,
                'bytes_uploaded', s.bytes_uploaded
            ),
            'highlights', named_struct(
                'peak_hour', named_struct(
                    'hour', p.hour, 'event_count', p.event_count
                ),
                'most_active_users', u.users
            ),
            'document_metrics', named_struct(
                'created', s.documents_created,
                'edited', s.documents_edited,
                'comments', s.comments_added
            ),
            'file_metrics', named_struct(
                'uploaded', s.files_uploaded,
                'shared', s.files_shared,
                'deleted', s.files_deleted,
                'bytes_uploaded', s.bytes_uploaded
            )
        )) AS report_json
    FROM (
        SELECT
            COUNT(DISTINCT CASE WHEN resolved_user_id <> 'unknown'
                                THEN resolved_user_id END) AS active_users,
            COUNT(DISTINCT CASE WHEN event_type IN ('document_created', 'document_edited')
                                THEN documentId END) AS active_documents,
            COUNT(DISTINCT CASE WHEN event_type IN ('file_uploaded', 'file_shared', 'file_deleted')
                                THEN fileId END) AS active_files,
            COUNT(*) AS total_events,
            COUNT_IF(event_type = 'document_created') AS documents_created,
            COUNT_IF(event_type = 'document_edited') AS documents_edited,
            COUNT_IF(event_type = 'comment_added') AS comments_added,
            COUNT_IF(event_type = 'file_uploaded') AS files_uploaded,
            COUNT_IF(event_type = 'file_shared') AS files_shared,
            COUNT_IF(event_type = 'file_deleted') AS files_deleted,
            COALESCE(SUM(CASE WHEN event_type = 'file_uploaded'
                              THEN sizeBytes END), 0) AS bytes_uploaded
        FROM analytics_events
    ) s
    CROSS JOIN (
        -- peak hour: most events in an hour; ties break to the earliest hour
        -- (legacy iterates the sorted hourly dict and keeps the first max)
        SELECT hour, SUM(n) AS event_count
        FROM (
            SELECT hour, event_type, COUNT(*) AS n
            FROM analytics_events
            GROUP BY hour, event_type
        )
        GROUP BY hour
        ORDER BY event_count DESC, hour ASC
        LIMIT 1
    ) p
    CROSS JOIN (
        -- most active users: top 5 by total actions; 'unknown' stays (legacy
        -- includes it) and the rank order is made explicit, not left to
        -- collect_list's input order
        SELECT transform(
            slice(
                array_sort(
                    collect_list(named_struct('total', total, 'user_id', user_id)),
                    (a, b) -> CASE
                        WHEN a.total <> b.total THEN sign(b.total - a.total)
                        WHEN a.user_id < b.user_id THEN -1
                        WHEN a.user_id > b.user_id THEN 1
                        ELSE 0
                    END
                ),
                1, 5
            ),
            x -> x.user_id
        ) AS users
        FROM (
            SELECT resolved_user_id AS user_id, COUNT(*) AS total
            FROM analytics_events
            GROUP BY resolved_user_id
        )
    ) u
    WHERE s.total_events > 0
) AS src
ON tgt.s3_key = src.s3_key
WHEN MATCHED THEN UPDATE SET
    report_type = src.report_type,
    report_date = src.report_date,
    generated_at = CURRENT_TIMESTAMP(),
    report_json = src.report_json
WHEN NOT MATCHED THEN INSERT (
    s3_key, report_type, report_date, generated_at, report_json
) VALUES (
    src.s3_key, src.report_type, src.report_date, src.generated_at,
    src.report_json
);

-- Per-user activity artifact (legacy top_users.jsonl.gz): one row per user,
-- serialized as the JSONL payload so downstream readers keep per-user
-- activity after cutover.
MERGE INTO ow_tp.ow_tp_analytics.analytics_daily_report AS tgt
USING (
    SELECT
        a.s3_key,
        a.artifact_type AS report_type,
        CAST(:ds AS DATE) AS report_date,
        CURRENT_TIMESTAMP() AS generated_at,
        to_json(named_struct(
            'report_type', a.artifact_type,
            'report_date', :ds,
            'generated_at', CAST(CURRENT_TIMESTAMP() AS STRING),
            'users', collect_list(named_struct(
                'user_id', u.resolved_user_id,
                'total', u.total,
                'actions', u.actions
            ))
        )) AS report_json
    FROM (
        SELECT
            resolved_user_id,
            COUNT(*) AS total,
            transform(
                collect_list(named_struct('event_type', event_type, 'hour', hour)),
                x -> named_struct('event_type', x.event_type, 'hour', x.hour)
            ) AS actions
        FROM analytics_events
        GROUP BY resolved_user_id
        ORDER BY total DESC, resolved_user_id ASC
        LIMIT 100
    ) u
    CROSS JOIN analytics_artifacts a
    WHERE a.artifact_type = 'analytics_top_users'
    GROUP BY a.s3_key, a.artifact_type
) AS src
ON tgt.s3_key = src.s3_key
WHEN MATCHED THEN UPDATE SET
    report_type = src.report_type,
    report_date = src.report_date,
    generated_at = CURRENT_TIMESTAMP(),
    report_json = src.report_json
WHEN NOT MATCHED THEN INSERT (
    s3_key, report_type, report_date, generated_at, report_json
) VALUES (
    src.s3_key, src.report_type, src.report_date, src.generated_at,
    src.report_json
);

-- Hourly breakdown artifact (legacy hourly_breakdown.json.gz).
MERGE INTO ow_tp.ow_tp_analytics.analytics_daily_report AS tgt
USING (
    SELECT
        a.s3_key,
        a.artifact_type AS report_type,
        CAST(:ds AS DATE) AS report_date,
        CURRENT_TIMESTAMP() AS generated_at,
        to_json(named_struct(
            'report_type', a.artifact_type,
            'report_date', :ds,
            'generated_at', CAST(CURRENT_TIMESTAMP() AS STRING),
            'hourly', collect_list(named_struct(
                'hour', h.hour,
                'total', h.total,
                'by_type', h.by_type
            ))
        )) AS report_json
    FROM (
        SELECT
            hour,
            COUNT(*) AS total,
            map_from_entries(collect_list(named_struct('key', event_type, 'value', n)))
                AS by_type
        FROM (
            SELECT hour, event_type, COUNT(*) AS n
            FROM analytics_events
            GROUP BY hour, event_type
        )
        GROUP BY hour
    ) h
    CROSS JOIN analytics_artifacts a
    WHERE a.artifact_type = 'analytics_hourly_breakdown'
    GROUP BY a.s3_key, a.artifact_type
) AS src
ON tgt.s3_key = src.s3_key
WHEN MATCHED THEN UPDATE SET
    report_type = src.report_type,
    report_date = src.report_date,
    generated_at = CURRENT_TIMESTAMP(),
    report_json = src.report_json
WHEN NOT MATCHED THEN INSERT (
    s3_key, report_type, report_date, generated_at, report_json
) VALUES (
    src.s3_key, src.report_type, src.report_date, src.generated_at,
    src.report_json
);
