-- The retention team's reports (migration/source/oracle/ddl/070 V_POLICY_LINEAGE, 080 V_ELIGIBLE_DOCS /
-- V_CLASS_TOTALS / V_LEGAL_HOLDS) over ARCH.*, set-based: the Oracle views call RETENTION_PKG once per row, these
-- join ARCH.V_POLICY_RESOLUTION / ARCH.V_POLICY_LINEAGE per NAMESPACE and use the 200 kernels, so they return the
-- same rows and values as the per-row UDFs. Same columns as the source views, prefixed by NAMESPACE. Timestamps are
-- TIMESTAMP(9) (ARCH.TS9). Keys and OWNER_NAME are right-trimmed as promoted (manifest `trim: right`). Idempotent.

-- CONNECT BY NOCYCLE PRIOR SUCCESSOR_CODE = POLICY_CODE, every code a root, leaves only. NOCYCLE stops before a row
-- whose SUCCESSOR_CODE already occurs on the path (Oracle's loop test is on the CONNECT BY PRIOR column), so a cycle
-- ends at its last distinct row and a dangling successor ends at the row naming it; no hop limit (RESOLVE_CLASS
-- raises -20002/-20003 for those, V_POLICY_RESOLUTION carries that outcome).
CREATE OR REPLACE VIEW ARCH.V_POLICY_LINEAGE AS
WITH RECURSIVE WALK (NAMESPACE, ROOT_CODE, DEPTH, CUR_CODE, NEXT_KEY, PATH_CODES, PATH_SUCCESSORS) AS (
    SELECT p.NAMESPACE, p.POLICY_CODE, 0, p.POLICY_CODE, COALESCE(RTRIM(p.SUCCESSOR_CODE), ''),
           ARRAY_CONSTRUCT(RTRIM(p.POLICY_CODE)), ARRAY_CONSTRUCT(COALESCE(RTRIM(p.SUCCESSOR_CODE), ''))
      FROM ARCH.RETNPLCY p
     WHERE p.POLICY_CODE IS NOT NULL
    UNION ALL
    SELECT w.NAMESPACE, w.ROOT_CODE, w.DEPTH + 1, p.POLICY_CODE, COALESCE(RTRIM(p.SUCCESSOR_CODE), ''),
           ARRAY_APPEND(w.PATH_CODES, RTRIM(p.POLICY_CODE)),
           ARRAY_APPEND(w.PATH_SUCCESSORS, COALESCE(RTRIM(p.SUCCESSOR_CODE), ''))
      FROM WALK w
      JOIN ARCH.RETNPLCY p ON p.NAMESPACE = w.NAMESPACE AND RTRIM(p.POLICY_CODE) = w.NEXT_KEY
     WHERE w.NEXT_KEY <> ''
       AND NOT ARRAY_CONTAINS(COALESCE(RTRIM(p.SUCCESSOR_CODE), '')::VARIANT, w.PATH_SUCCESSORS)
)
SELECT NAMESPACE,
       RPAD(RTRIM(ROOT_CODE), 4)                                                           AS POLICY_CODE,
       RPAD(RTRIM(CUR_CODE), 4)                                                            AS SOR_CODE,
       DEPTH                                                                               AS HOPS,
       ARRAY_TO_STRING(PATH_CODES, '>')                                                    AS LINEAGE,
       IFF(ARRAY_CONTAINS(RTRIM(CUR_CODE)::VARIANT, ARCH.CLOSED_SCHEDULE()), 1, 0)         AS IN_CLOSED_SCHEDULE
  FROM WALK
QUALIFY ROW_NUMBER() OVER (PARTITION BY NAMESPACE, ROOT_CODE ORDER BY DEPTH DESC) = 1;

-- Rows due for destruction in the current cycle (as of 2026-01-01), with the derived dates the report shows.
-- WHERE = RETENTION_PKG.IS_ELIGIBLE(...) = 1: the hold wins before resolution; a non-held row whose class does not
-- resolve fails the query with the package error, as the Oracle view does.
CREATE OR REPLACE VIEW ARCH.V_ELIGIBLE_DOCS AS
SELECT d.NAMESPACE,
       d.ARCH_KEY,
       d.DOC_ID,
       d.VERSION_NO,
       d.RETENTION_CLASS,
       r.SOR_CODE                                                                          AS SOR_CLASS,
       ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL)                             AS LAST_ACCESS_TS,
       d.STORAGE_CHARGE,
       d.BYTE_SIZE,
       d.LEGAL_HOLD_FLAG,
       ARCH.ADD_RETENTION_YEARS(ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL), r.RETENTION_YEARS)
                                                                                           AS DISPOSITION_DUE,
       TO_CHAR(d.DISPOSITION_DT, 'YYYYMMDD')                                               AS DISPOSITION_DT_STORED,
       ARCH.DISPOSITION_CODE_OF(
           d.LEGAL_HOLD_FLAG, r.DISPOSITION_ACTION,
           IFF(r.DISPOSITION_ACTION = 'PERM', NULL,
               ARCH.ADD_RETENTION_YEARS(ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL), r.RETENTION_YEARS)),
           '2026-01-01'::DATE)                                                             AS DISPOSITION_CODE
  FROM ARCH.DOCARCH d
  LEFT JOIN ARCH.V_POLICY_RESOLUTION r
    ON r.NAMESPACE = d.NAMESPACE AND r.POLICY_KEY = RTRIM(d.RETENTION_CLASS)
 WHERE CASE
           WHEN COALESCE(d.LEGAL_HOLD_FLAG, 'N') = 'Y' THEN 0
           WHEN r.STATUS IS DISTINCT FROM 'RESOLVED' THEN ARCH.RESOLUTION_ERROR(
               OBJECT_CONSTRUCT_KEEP_NULL('STATUS', r.STATUS, 'UNKNOWN_CODE', r.UNKNOWN_CODE),
               d.RETENTION_CLASS)::NUMBER
           WHEN r.IN_CLOSED_SCHEDULE = 1
                AND ARCH.PLSQL_TS6(ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL)) < ARCH.CUTOFF_TS() THEN 1
           ELSE 0
       END = 1;

-- Per system-of-record class over the eligible population (RETENTION_PKG.CLASS_TOTALS plus the access range).
CREATE OR REPLACE VIEW ARCH.V_CLASS_TOTALS AS
SELECT d.NAMESPACE,
       l.SOR_CODE                                                                          AS RETENTION_CLASS,
       COUNT(*)                                                                            AS DOC_COUNT,
       ROUND(SUM(d.STORAGE_CHARGE), 8)                                                     AS CHARGE_TOTAL,
       MIN(ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL))                        AS OLDEST_ACCESS_TS,
       MAX(ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL))                        AS NEWEST_ACCESS_TS
  FROM ARCH.DOCARCH d
  JOIN ARCH.V_POLICY_LINEAGE l
    ON l.NAMESPACE = d.NAMESPACE AND RTRIM(l.POLICY_CODE) = RTRIM(d.RETENTION_CLASS)
 WHERE l.IN_CLOSED_SCHEDULE = 1
   AND d.LEGAL_HOLD_FLAG = 'N'
   AND ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL) < ARCH.CUTOFF_TS()
 GROUP BY d.NAMESPACE, l.SOR_CODE;

-- RETENTION_PKG.CLASS_TOTALS(p_as_of) RETURN SYS_REFCURSOR: the same aggregate for any as-of date, as a table
-- function (SELECT * FROM TABLE(ARCH.CLASS_TOTALS('2026-01-01'::DATE)) ORDER BY NAMESPACE, RETENTION_CLASS).
CREATE OR REPLACE FUNCTION ARCH.CLASS_TOTALS(P_AS_OF DATE DEFAULT '2026-01-01'::DATE)
RETURNS TABLE (NAMESPACE VARCHAR, RETENTION_CLASS VARCHAR, DOC_COUNT NUMBER, CHARGE_TOTAL NUMBER(38, 8))
AS $$
    SELECT d.NAMESPACE, l.SOR_CODE, COUNT(*), ROUND(SUM(d.STORAGE_CHARGE), 8)
      FROM ARCH.DOCARCH d
      JOIN ARCH.V_POLICY_LINEAGE l
        ON l.NAMESPACE = d.NAMESPACE AND RTRIM(l.POLICY_CODE) = RTRIM(d.RETENTION_CLASS)
     WHERE l.IN_CLOSED_SCHEDULE = 1
       AND d.LEGAL_HOLD_FLAG = 'N'
       AND ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL) < ARCH.CUTOFF_TS(P_AS_OF)
     GROUP BY d.NAMESPACE, l.SOR_CODE
$$;

-- Documents under legal hold, with the last HOLD event that put them there (if any survived).
CREATE OR REPLACE VIEW ARCH.V_LEGAL_HOLDS AS
SELECT d.NAMESPACE,
       d.ARCH_KEY,
       d.DOC_ID,
       d.RETENTION_CLASS,
       ARCH.TS9(d.LAST_ACCESS_TS, d.LAST_ACCESS_TS_NANOS_TAIL)                             AS LAST_ACCESS_TS,
       COALESCE(d.OWNER_NAME, '?')                                                         AS OWNER_NAME,
       f.LAST_HOLD_TS,
       COALESCE(f.AUDIT_EVENTS, 0)                                                         AS AUDIT_EVENTS
  FROM ARCH.DOCARCH d
  LEFT JOIN (
      SELECT NAMESPACE,
             RTRIM(ARCH_KEY)                                                               AS ARCH_KEY,
             MAX(IFF(EVENT_TYPE = 'HOLD', ARCH.TS9(EVENT_TS, EVENT_TS_NANOS_TAIL), NULL))  AS LAST_HOLD_TS,
             COUNT(*)                                                                      AS AUDIT_EVENTS
        FROM ARCH.FILEAUD
       GROUP BY NAMESPACE, RTRIM(ARCH_KEY)
  ) f ON f.NAMESPACE = d.NAMESPACE AND f.ARCH_KEY = RTRIM(d.ARCH_KEY)
 WHERE d.LEGAL_HOLD_FLAG = 'Y';
