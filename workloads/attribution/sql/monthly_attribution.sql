-- Monthly credits by client-side ID, workload, commit and phase.
-- Needs a role with USAGE_VIEWER (or GOVERNANCE_VIEWER) on the SNOWFLAKE database.
-- QUERY_ATTRIBUTION_HISTORY lags by up to eight hours and excludes warehouse idle time;
-- the second query reports idle time per workload warehouse. A month that has not been
-- reported yet is written as `pending` in provenance.yaml, never as 0.

-- 1. Attributed compute per label.
SELECT
    DATE_TRUNC('month', q.start_time)                 AS month,
    TRY_PARSE_JSON(q.query_tag):csid::STRING          AS csid,
    TRY_PARSE_JSON(q.query_tag):workload::STRING      AS workload,
    TRY_PARSE_JSON(q.query_tag):commit::STRING        AS commit,
    TRY_PARSE_JSON(q.query_tag):phase::STRING         AS phase,
    q.warehouse_name,
    q.user_name,
    COUNT(*)                                          AS query_count,
    SUM(q.credits_attributed_compute
        + COALESCE(q.credits_used_query_acceleration, 0)) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY q
WHERE q.warehouse_name LIKE 'WH\\_%'
  AND q.start_time >= DATEADD('month', -1, DATE_TRUNC('month', CURRENT_DATE()))
GROUP BY ALL
ORDER BY month, workload, csid, phase, commit;

-- 2. Idle time per workload warehouse: metered compute minus attributed compute.
WITH metered AS (
    SELECT DATE_TRUNC('month', start_time) AS month, warehouse_name,
           SUM(credits_used_compute) AS credits_metered
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE warehouse_name LIKE 'WH\\_%'
    GROUP BY ALL
), attributed AS (
    SELECT DATE_TRUNC('month', start_time) AS month, warehouse_name,
           SUM(credits_attributed_compute) AS credits_attributed
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
    WHERE warehouse_name LIKE 'WH\\_%'
    GROUP BY ALL
)
SELECT m.month, m.warehouse_name, t.tag_value AS devin_csid,
       m.credits_metered, COALESCE(a.credits_attributed, 0) AS credits_attributed,
       m.credits_metered - COALESCE(a.credits_attributed, 0) AS credits_idle
FROM metered m
LEFT JOIN attributed a USING (month, warehouse_name)
LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
       ON t.domain = 'WAREHOUSE' AND t.object_name = m.warehouse_name
      AND t.tag_name = 'DEVIN_CSID' AND t.object_deleted IS NULL
ORDER BY m.month, m.warehouse_name;

-- 3. Labeling gaps: queries on a workload warehouse without a parseable csid tag,
--    or from a client other than Devin_Demo. Both should return no rows.
SELECT q.query_id, q.user_name, q.warehouse_name, q.query_tag, q.start_time
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY q
WHERE q.warehouse_name LIKE 'WH\\_%'
  AND TRY_PARSE_JSON(q.query_tag):csid IS NULL;

-- The connector sends `application` in CLIENT_ENVIRONMENT; confirm the key on a live session before
-- relying on this check.
SELECT s.session_id, s.user_name, s.client_application_id,
       PARSE_JSON(s.client_environment):APPLICATION::STRING AS application
FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
WHERE s.user_name LIKE 'SVC\\_CS\\_%'
  AND COALESCE(PARSE_JSON(s.client_environment):APPLICATION::STRING, '') <> 'Devin_Demo';
