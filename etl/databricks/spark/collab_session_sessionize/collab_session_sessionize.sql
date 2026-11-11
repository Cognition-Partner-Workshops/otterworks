/* run=dbx-d1111 act=spark step=job consumer=collab_session_sessionize */
-- run_token=dbx-d1111 expires=2026-11-24
-- Databricks SQL re-expression of etl/spark/jobs/py/collab_session_sessionize.py.
-- Per (USER_ID, DOCUMENT_ID): order EVENT_AT, open a new session when the gap to the previous event
-- exceeds 1800 seconds; SESSION_NUMBER starts at 1; START_AT/END_AT are the first/last event of the session.
-- Python sorted() raises on NULL timestamps in groups with more than one event; that case fails here too.
-- A group with a single NULL event yields one session with NULL START_AT/END_AT, as in the source.
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__spark_collab_session_sessionize
  COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/collab_session_sessionize.py'
  TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS
WITH events AS (
  -- inputs.sql
  SELECT session_id            AS COLLAB_SESSION_ID,
         document_id           AS DOCUMENT_ID,
         user_id               AS USER_ID,
         CAST(NULL AS STRING)  AS SESSION_ID,
         start_ts              AS EVENT_AT
  FROM cpw.dbx_d1111_before.documents__collab_session
),
checked AS (
  SELECT USER_ID, DOCUMENT_ID,
         CASE WHEN count(*) OVER (PARTITION BY USER_ID, DOCUMENT_ID) > 1
                   AND count(EVENT_AT) OVER (PARTITION BY USER_ID, DOCUMENT_ID) < count(*) OVER (PARTITION BY USER_ID, DOCUMENT_ID)
              THEN raise_error('NULL EVENT_AT in a multi-event group (source job fails on sorted())')
              ELSE EVENT_AT END AS EVENT_AT
  FROM events
),
gaps AS (
  SELECT USER_ID, DOCUMENT_ID, EVENT_AT,
         CASE WHEN unix_micros(EVENT_AT)
                   - unix_micros(lag(EVENT_AT) OVER (PARTITION BY USER_ID, DOCUMENT_ID ORDER BY EVENT_AT)) > 1800000000
              THEN 1 ELSE 0 END AS NEW_SESSION
  FROM checked
),
numbered AS (
  SELECT USER_ID, DOCUMENT_ID, EVENT_AT,
         1 + sum(NEW_SESSION) OVER (PARTITION BY USER_ID, DOCUMENT_ID ORDER BY EVENT_AT
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS SESSION_NUMBER
  FROM gaps
)
SELECT CAST(USER_ID AS BIGINT) AS USER_ID, CAST(DOCUMENT_ID AS BIGINT) AS DOCUMENT_ID, CAST(SESSION_NUMBER AS BIGINT) AS SESSION_NUMBER,
       CAST(min(EVENT_AT) AS TIMESTAMP) AS START_AT, CAST(max(EVENT_AT) AS TIMESTAMP) AS END_AT
FROM numbered
GROUP BY USER_ID, DOCUMENT_ID, SESSION_NUMBER;
