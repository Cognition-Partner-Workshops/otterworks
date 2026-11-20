-- The half-open bounds select the full 90-day branch fixture in the emulator.
-- Runtime smoke tests execute outside this window.
SELECT upper(o.ObjectDatabaseName || '.' || o.ObjectTableName) AS object,
       q.UserName AS principal,
       upper(o.UsageType) AS usage,
       count(DISTINCT q.QueryID) FILTER (WHERE q.ErrorCode = 0) AS successful,
       count(DISTINCT q.QueryID) FILTER (WHERE q.ErrorCode <> 0) AS failed,
       count(DISTINCT q.QueryID) FILTER (
           WHERE q.ErrorCode = 0 AND q.StartTime < TIMESTAMP '2026-08-13'
       ) AS first_day_successful,
       max(q.StartTime) FILTER (WHERE q.ErrorCode = 0) AS last_success,
       array_agg(DISTINCT q.AppID ORDER BY q.AppID) AS applications
FROM DBC.QryLogV q
JOIN DBC.QryLogObjectsV o ON o.QueryID = q.QueryID
WHERE q.StartTime >= TIMESTAMP '2026-08-12'
  AND q.StartTime < TIMESTAMP '2026-11-10'
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
