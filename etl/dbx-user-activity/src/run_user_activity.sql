-- ow_tp_analytics_user_activity / run_user_activity
-- Conversion of etl/scripts/user_activity_daily.py (Postgres
-- otterworks_analytics.analytics_daily_summary aggregates + per-user S3
-- analytics/daily/year=<y>/month=<m>/day=<d>/top_users.jsonl.gz reads ->
-- reports/user-activity report for admin-service) to Lakeflow SQL.
--
-- Snapshot posture (plan decision parity-mechanism): legacy inputs land in
-- ow_tp.ow_tp_analytics_src. The Postgres summary mirror is
-- analytics_daily_summary; the per-user S3 files are mirrored as report_json
-- rows of analytics_daily_report keyed by their legacy s3 path (plan decision
-- analytics-daily-artifacts: mirror). The declared parity surface
-- (ow_tp_analytics_src.user_activity_report) covers only the per-user metric
-- rows of user_summaries; the report-level trends and daily_summaries lists
-- are not staged and are not reproduced here.
--
-- Legacy window: the S3 loop iterates day_offset 0..29, i.e. file days in
-- [ds-29, ds]. Missing days are silently skipped in legacy (bare except),
-- so absent artifact rows are simply unrepresented. user_id falls back to
-- 'unknown' and total to 0 on missing fields, actions to {}.
--
-- Idempotent: MERGE on (report_date, user_id, metric); a rerun of the same
-- :ds converges to the same rows. Rows of report_date=:ds no longer produced
-- are deleted (legacy rewrites the dated report wholesale); rows of other
-- dates are untouched, matching the dated-file model.
--
-- Parameters: :ds (run date, 'YYYY-MM-DD').

WITH artifacts AS (
    SELECT
        make_date(
            CAST(regexp_extract(s3_key, 'year=([0-9]+)', 1) AS INT),
            CAST(regexp_extract(s3_key, 'month=([0-9]+)', 1) AS INT),
            CAST(regexp_extract(s3_key, 'day=([0-9]+)', 1) AS INT)
        ) AS file_day,
        report_json
    FROM ow_tp.ow_tp_analytics_src.analytics_daily_report
    WHERE s3_key LIKE 'analytics/daily/year=%/month=%/day=%/top_users.jsonl.gz'
),
windowed AS (
    -- file_day NULL on an unparseable key falls out of the BETWEEN the same
    -- way legacy's missing-key except skips it
    SELECT file_day, report_json
    FROM artifacts
    WHERE file_day BETWEEN date_sub(CAST(:ds AS DATE), 29)
                      AND CAST(:ds AS DATE)
),
lines AS (
    -- report_json carries the decompressed top_users.jsonl.gz verbatim:
    -- one JSON object per line, blank lines skipped like legacy's
    -- `if not line: continue`
    SELECT file_day, trim(line) AS raw
    FROM windowed
    LATERAL VIEW explode(split(report_json, '\n')) AS line
    WHERE trim(line) <> ''
),
per_user AS (
    SELECT
        file_day,
        COALESCE(j.user_id, 'unknown') AS user_id,
        COALESCE(j.total, 0) AS total,
        j.actions AS actions
    FROM (
        SELECT
            file_day,
            from_json(
                raw,
                'user_id STRING, total BIGINT, actions MAP<STRING,BIGINT>'
            ) AS j
        FROM lines
    )
    WHERE j IS NOT NULL
),
agg AS (
    -- legacy accumulation: total_actions += total per day present,
    -- active_days += 1 per file the user appears in
    SELECT
        user_id,
        SUM(total) AS total_actions,
        COUNT(DISTINCT file_day) AS active_days
    FROM per_user
    GROUP BY user_id
),
by_type AS (
    -- actions_by_type: summed per action key; absent keys emit no row
    -- (legacy only iterates the keys present in the day's actions map)
    SELECT
        user_id,
        action_type,
        SUM(action_count) AS n
    FROM per_user
    LATERAL VIEW explode(actions) AS action_type, action_count
    GROUP BY user_id, action_type
),
metric_rows AS (
    SELECT user_id, 'total_actions' AS metric,
           CAST(total_actions AS STRING) AS metric_value
    FROM agg
    UNION ALL
    SELECT user_id, 'active_days',
           CAST(active_days AS STRING)
    FROM agg
    UNION ALL
    SELECT user_id, concat('actions_by_type.', action_type),
           CAST(n AS STRING)
    FROM by_type
)
MERGE INTO ow_tp.ow_tp_analytics.user_activity_report AS tgt
USING (
    SELECT
        CAST(:ds AS DATE) AS report_date,
        user_id,
        metric,
        metric_value,
        CURRENT_TIMESTAMP() AS generated_at
    FROM metric_rows
) AS src
ON tgt.report_date = src.report_date
   AND tgt.user_id = src.user_id
   AND tgt.metric = src.metric
WHEN MATCHED THEN UPDATE SET
    metric_value = src.metric_value,
    generated_at = src.generated_at
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE AND tgt.report_date = CAST(:ds AS DATE)
    THEN DELETE;
