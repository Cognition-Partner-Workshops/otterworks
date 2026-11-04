-- Consumption ledger: one row per client-side ID (csid), read only from SNOWFLAKE.ACCOUNT_USAGE.
-- Needs a role with USAGE_VIEWER or GOVERNANCE_VIEWER on the SNOWFLAKE database.
-- Run with run_ledger.py, which executes the statements below in order and writes output/.
--
-- Join key: the csid, phase and commit inside each query's QUERY_TAG (compact JSON, see
-- workloads/attribution/README.md on the attribution branch). Registration: a csid is registered when
-- it is the DEVIN_CSID object tag value of a warehouse (TAG_REFERENCES), which is the only workload
-- registry Snowflake itself holds.
--
-- pending is not zero. A credit figure is a number only when the view it comes from has landed
-- every query of that csid and phase, otherwise it is the string pending:
--   dev / runtime credits  QUERY_ATTRIBUTION_HISTORY, complete once its newest end_time passes the
--                          csid's last query of that phase (lag up to ~8h)
--   cortex_ai_credits      CORTEX_AI_FUNCTIONS_USAGE_HISTORY (hourly buckets), complete once its
--                          newest bucket start passes the csid's last query
--   warehouse_metered      WAREHOUSE_METERING_HISTORY for the csid's DEVIN_CSID warehouse, closed hours
--                          only, compute plus cloud services, idle time included, reported through
--                          metering_through (statement 2)

SET ledger_from = '2026-11-04 00:00:00 +0000';

-- 1. The ledger.
WITH labeled AS (
    SELECT q.query_id, q.session_id, q.warehouse_name, q.start_time, q.end_time,
           TRY_PARSE_JSON(q.query_tag):csid::STRING     AS csid,
           TRY_PARSE_JSON(q.query_tag):workload::STRING AS workload,
           TRY_PARSE_JSON(q.query_tag):phase::STRING    AS phase,
           TRY_PARSE_JSON(q.query_tag):commit::STRING   AS commit_sha
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    WHERE q.start_time >= $ledger_from::TIMESTAMP_LTZ
      AND TRY_PARSE_JSON(q.query_tag):csid IS NOT NULL
), marks AS (
    SELECT
        (SELECT MAX(end_time) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
          WHERE start_time >= $ledger_from::TIMESTAMP_LTZ)                          AS qh_through,
        (SELECT MAX(end_time) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
          WHERE start_time >= DATEADD('day', -2, $ledger_from::TIMESTAMP_LTZ))      AS qah_through,
        (SELECT MAX(start_time) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
          WHERE start_time >= DATEADD('day', -2, $ledger_from::TIMESTAMP_LTZ))      AS ai_through
), registry AS (
    SELECT TRIM(s.value::STRING) AS csid, r.object_name AS warehouse_name
    FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES r,
         TABLE(SPLIT_TO_TABLE(r.tag_value, ',')) s
    WHERE r.tag_name = 'DEVIN_CSID' AND r.domain = 'WAREHOUSE' AND r.object_deleted IS NULL
), all_csids AS (
    SELECT csid FROM labeled
    UNION
    SELECT csid FROM registry
), per_csid AS (
    SELECT csid,
           MODE(workload)                                       AS workload,
           COUNT_IF(phase = 'dev')                              AS dev_queries,
           COUNT_IF(phase = 'runtime')                          AS runtime_queries,
           MAX(IFF(phase = 'dev', end_time, NULL))              AS dev_last_end,
           MAX(IFF(phase = 'runtime', end_time, NULL))          AS runtime_last_end,
           MAX(end_time)                                        AS last_end,
           COUNT_IF(NOT RLIKE(COALESCE(commit_sha, ''), '[0-9a-f]{40}')) AS bad_commit_queries,
           COUNT(DISTINCT session_id)                           AS sessions
    FROM labeled
    GROUP BY csid
), commits AS (
    SELECT csid, phase, COUNT(*) AS n,
           LISTAGG(commit_sha, ' ') WITHIN GROUP (ORDER BY first_seen) AS commits
    FROM (SELECT csid, phase, commit_sha, MIN(start_time) AS first_seen
          FROM labeled
          WHERE RLIKE(commit_sha, '[0-9a-f]{40}')
          GROUP BY 1, 2, 3)
    GROUP BY 1, 2
), attributed AS (
    SELECT l.csid, l.phase,
           SUM(a.credits_attributed_compute + COALESCE(a.credits_used_query_acceleration, 0)) AS credits
    FROM labeled l
    JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY a ON a.query_id = l.query_id
    WHERE a.start_time >= $ledger_from::TIMESTAMP_LTZ
    GROUP BY 1, 2
), ai AS (
    SELECT l.csid, SUM(c.credits) AS credits
    FROM labeled l
    JOIN SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY c ON c.query_id = l.query_id
    WHERE c.start_time >= DATEADD('hour', -1, $ledger_from::TIMESTAMP_LTZ)
    GROUP BY 1
), metered AS (
    SELECT g.csid,
           LISTAGG(DISTINCT g.warehouse_name, ' ') AS warehouses,
           SUM(w.credits_used)                     AS credits
    FROM registry g
    LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY w
           ON w.warehouse_name = g.warehouse_name
          AND w.start_time >= $ledger_from::TIMESTAMP_LTZ
          AND w.end_time <= CURRENT_TIMESTAMP()
    GROUP BY 1
), apps AS (
    SELECT l.csid,
           LISTAGG(DISTINCT COALESCE(TRY_PARSE_JSON(s.client_environment):APPLICATION::STRING, '(none)'), ', ')
               WITHIN GROUP (ORDER BY COALESCE(TRY_PARSE_JSON(s.client_environment):APPLICATION::STRING, '(none)')) AS applications,
           COUNT(DISTINCT l.session_id) AS sessions_landed
    FROM labeled l
    JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s ON s.session_id = l.session_id
    GROUP BY 1
)
SELECT
    c.csid,
    p.workload,
    IFF(COALESCE(p.runtime_queries, 0) > 0, 'runtime', 'dev')           AS stage,
    IFF(mt.csid IS NOT NULL, 'registered', 'unregistered')              AS registry,
    mt.warehouses                                                       AS devin_csid_warehouse,
    COALESCE(p.dev_queries, 0)                                          AS dev_queries,
    COALESCE(p.runtime_queries, 0)                                      AS runtime_queries,
    CASE WHEN COALESCE(p.dev_queries, 0) = 0
              THEN IFF(m.qah_through >= m.qh_through, '0', 'pending')
         WHEN m.qah_through >= p.dev_last_end
              THEN TO_VARCHAR(ROUND(COALESCE(ad.credits, 0), 6))
         ELSE 'pending' END                                             AS dev_credits,
    CASE WHEN COALESCE(p.runtime_queries, 0) = 0
              THEN IFF(m.qah_through >= m.qh_through, '0', 'pending')
         WHEN m.qah_through >= p.runtime_last_end
              THEN TO_VARCHAR(ROUND(COALESCE(ar.credits, 0), 6))
         ELSE 'pending' END                                             AS runtime_credits,
    CASE WHEN p.last_end IS NULL
              THEN IFF(m.ai_through >= m.qh_through, '0', 'pending')
         WHEN m.ai_through >= p.last_end
              THEN TO_VARCHAR(ROUND(COALESCE(ai.credits, 0), 6))
         ELSE 'pending' END                                             AS cortex_ai_credits,
    IFF(mt.csid IS NULL, 'n/a', TO_VARCHAR(ROUND(COALESCE(mt.credits, 0), 6))) AS warehouse_metered_credits,
    ROUND(COALESCE(ad.credits, 0), 6)                                   AS dev_credits_landed,
    ROUND(COALESCE(ar.credits, 0), 6)                                   AS runtime_credits_landed,
    ROUND(COALESCE(ai.credits, 0), 6)                                   AS cortex_ai_credits_landed,
    COALESCE(cd.n, 0)                                                   AS dev_commit_count,
    cd.commits                                                          AS dev_commits,
    COALESCE(cr.n, 0)                                                   AS runtime_commit_count,
    cr.commits                                                          AS runtime_commits,
    COALESCE(p.bad_commit_queries, 0)                                   AS queries_without_full_sha,
    COALESCE(p.sessions, 0)                                             AS sessions,
    COALESCE(a.sessions_landed, 0)                                      AS sessions_landed,
    a.applications                                                      AS applications
FROM all_csids c
CROSS JOIN marks m
LEFT JOIN per_csid   p  ON p.csid = c.csid
LEFT JOIN metered    mt ON mt.csid = c.csid
LEFT JOIN attributed ad ON ad.csid = c.csid AND ad.phase = 'dev'
LEFT JOIN attributed ar ON ar.csid = c.csid AND ar.phase = 'runtime'
LEFT JOIN ai            ON ai.csid = c.csid
LEFT JOIN commits    cd ON cd.csid = c.csid AND cd.phase = 'dev'
LEFT JOIN commits    cr ON cr.csid = c.csid AND cr.phase = 'runtime'
LEFT JOIN apps       a  ON a.csid = c.csid
ORDER BY registry, c.csid;

-- 2. How far each view has landed.
SELECT
    $ledger_from::TIMESTAMP_LTZ                                                   AS ledger_from,
    CURRENT_TIMESTAMP()                                                           AS generated_at,
    (SELECT MAX(end_time) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
      WHERE start_time >= $ledger_from::TIMESTAMP_LTZ)                            AS query_history_through,
    (SELECT MAX(end_time) FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
      WHERE start_time >= DATEADD('day', -2, $ledger_from::TIMESTAMP_LTZ))        AS attribution_through,
    (SELECT MAX(start_time) FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
      WHERE start_time >= DATEADD('day', -2, $ledger_from::TIMESTAMP_LTZ))        AS cortex_ai_through,
    (SELECT MAX(end_time) FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
      WHERE start_time >= $ledger_from::TIMESTAMP_LTZ AND end_time <= CURRENT_TIMESTAMP()) AS metering_through,
    (SELECT MAX(created_on) FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS
      WHERE created_on >= $ledger_from::TIMESTAMP_LTZ)                            AS sessions_through;

-- 3. Labeling gaps: queries on a DEVIN_CSID warehouse whose QUERY_TAG has no parseable csid.
--    Their compute is metered on the workload warehouse but cannot be split by csid, phase or commit.
WITH registry AS (
    SELECT DISTINCT object_name AS warehouse_name
    FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
    WHERE tag_name = 'DEVIN_CSID' AND domain = 'WAREHOUSE' AND object_deleted IS NULL
)
SELECT q.warehouse_name,
       CASE WHEN q.user_name LIKE 'STPLATSTREAMLIT%' THEN 'Streamlit runtime user (STPLATSTREAMLIT*)'
            WHEN q.user_name = 'SYSTEM' THEN 'SYSTEM'
            WHEN q.user_name LIKE 'SFNFR\\_%' OR q.user_name LIKE 'SVC\\_%' THEN q.user_name
            ELSE '(other user)' END                                         AS user_class,
       q.role_name,
       CASE WHEN COALESCE(q.query_tag, '') = '' THEN 'empty'
            WHEN q.query_tag LIKE 'schemachange%' THEN 'schemachange prefix, no csid'
            WHEN TRY_PARSE_JSON(q.query_tag) IS NULL THEN 'not JSON'
            ELSE 'JSON without csid' END                                    AS tag_shape,
       COUNT(*)                                                             AS queries,
       ROUND(SUM(q.execution_time) / 1000, 1)                               AS execution_seconds,
       MIN(q.start_time)                                                    AS first_seen,
       MAX(q.start_time)                                                    AS last_seen
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN registry r ON r.warehouse_name = q.warehouse_name
WHERE q.start_time >= $ledger_from::TIMESTAMP_LTZ
  AND TRY_PARSE_JSON(q.query_tag):csid IS NULL
GROUP BY ALL
ORDER BY queries DESC;

-- 4. Registered csids running off their own warehouse. QUERY_ATTRIBUTION_HISTORY still credits these
--    queries to the csid, but the metered spend lands on someone else's warehouse.
WITH registry AS (
    SELECT TRIM(s.value::STRING) AS csid, r.object_name AS warehouse_name
    FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES r,
         TABLE(SPLIT_TO_TABLE(r.tag_value, ',')) s
    WHERE r.tag_name = 'DEVIN_CSID' AND r.domain = 'WAREHOUSE' AND r.object_deleted IS NULL
)
SELECT TRY_PARSE_JSON(q.query_tag):csid::STRING  AS csid,
       TRY_PARSE_JSON(q.query_tag):phase::STRING AS phase,
       COALESCE(q.warehouse_name, '(no warehouse)') AS warehouse_name,
       r.warehouse_name                          AS own_warehouse,
       COUNT(*)                                  AS queries,
       ROUND(SUM(q.execution_time) / 1000, 1)    AS execution_seconds
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN registry r ON r.csid = TRY_PARSE_JSON(q.query_tag):csid::STRING
WHERE q.start_time >= $ledger_from::TIMESTAMP_LTZ
  AND COALESCE(q.warehouse_name, '') <> r.warehouse_name
GROUP BY ALL
ORDER BY csid, queries DESC;
