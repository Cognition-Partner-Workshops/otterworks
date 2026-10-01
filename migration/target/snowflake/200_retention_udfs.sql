-- ARCHIVE.RETENTION_PKG (migration/source/oracle/ddl/070_archive_retention_pkg.sql) as Snowflake SQL UDFs over
-- ARCH.RETNPLCY. Same names, argument order, defaults and results as the package functions; errors keep the
-- package's RAISE_APPLICATION_ERROR codes and messages (surfaced as "<code>: <message>" in the error text).
-- The scalar UDFs read the policy table of every namespace in the tenant database (the package has no namespace
-- argument); the set-based views in 210 join per NAMESPACE. Nothing here writes or deletes. Idempotent.

-- RAISE_APPLICATION_ERROR(code, message): fails the calling statement with "<code>: <message>". The return type
-- only lets callers use it in any branch (::VARCHAR / ::NUMBER / ::OBJECT); it never returns.
CREATE OR REPLACE FUNCTION ARCH.RAISE_APPLICATION_ERROR(ERR_CODE FLOAT, ERR_MESSAGE VARCHAR)
RETURNS VARIANT
LANGUAGE JAVASCRIPT
AS $$
throw new Error(String(ERR_CODE) + ": " + (ERR_MESSAGE === null || ERR_MESSAGE === undefined ? "" : ERR_MESSAGE));
$$;

-- g_closed_schedule: the package-body associative array (hidden reference data on the source), made explicit.
CREATE OR REPLACE FUNCTION ARCH.CLOSED_SCHEDULE()
RETURNS ARRAY
AS $$
    ARRAY_CONSTRUCT('FIN7', 'LGL7', 'HRS7', 'TAX7', 'AUD7')
$$;

-- RESOLVE_CLASS's loop, set-based: one row per (NAMESPACE, POLICY_CODE) with the outcome of following
-- SUCCESSOR_CODE until a blank successor. CHAR(4) semantics: codes compare RTRIM-ed, a blank successor RTRIMs to ''.
-- STATUS: RESOLVED (SOR_CODE/HOPS/attributes of the resolved row), UNKNOWN (UNKNOWN_CODE is the successor that has
-- no RETNPLCY row: -20002), CYCLE (a ninth hop was needed: -20003, so cycles and over-long chains both land here).
CREATE OR REPLACE VIEW ARCH.V_POLICY_RESOLUTION AS
WITH RECURSIVE CHAIN (NAMESPACE, POLICY_KEY, DEPTH, CUR_KEY, NEXT_KEY, RETENTION_YEARS, DISPOSITION_ACTION) AS (
    SELECT p.NAMESPACE, RTRIM(p.POLICY_CODE), 0, RTRIM(p.POLICY_CODE), COALESCE(RTRIM(p.SUCCESSOR_CODE), ''),
           p.RETENTION_YEARS, RTRIM(p.DISPOSITION_ACTION)
      FROM ARCH.RETNPLCY p
    UNION ALL
    SELECT c.NAMESPACE, c.POLICY_KEY, c.DEPTH + 1, RTRIM(p.POLICY_CODE), COALESCE(RTRIM(p.SUCCESSOR_CODE), ''),
           p.RETENTION_YEARS, RTRIM(p.DISPOSITION_ACTION)
      FROM CHAIN c
      JOIN ARCH.RETNPLCY p ON p.NAMESPACE = c.NAMESPACE AND RTRIM(p.POLICY_CODE) = c.NEXT_KEY
     WHERE c.NEXT_KEY <> '' AND c.DEPTH < 8
)
SELECT NAMESPACE,
       POLICY_KEY,
       RPAD(POLICY_KEY, 4)                                                       AS POLICY_CODE,
       CASE WHEN NEXT_KEY = '' THEN 'RESOLVED' WHEN DEPTH = 8 THEN 'CYCLE' ELSE 'UNKNOWN' END AS STATUS,
       IFF(NEXT_KEY = '', RPAD(CUR_KEY, 4), NULL)                                AS SOR_CODE,
       IFF(NEXT_KEY = '', DEPTH, NULL)                                           AS HOPS,
       IFF(NEXT_KEY = '', RETENTION_YEARS, NULL)                                 AS RETENTION_YEARS,
       IFF(NEXT_KEY = '', DISPOSITION_ACTION, NULL)                              AS DISPOSITION_ACTION,
       IFF(NEXT_KEY = '', IFF(ARRAY_CONTAINS(CUR_KEY::VARIANT, ARCH.CLOSED_SCHEDULE()), 1, 0), NULL)
                                                                                 AS IN_CLOSED_SCHEDULE,
       IFF(NEXT_KEY <> '' AND DEPTH < 8, RPAD(NEXT_KEY, 4), NULL)                AS UNKNOWN_CODE
  FROM CHAIN
QUALIFY ROW_NUMBER() OVER (PARTITION BY NAMESPACE, POLICY_KEY ORDER BY DEPTH DESC) = 1;

-- TIMESTAMP(9) of an archive timestamp: TIMESTAMP_NTZ(6) + fraction digits 7-9 from <COL>_NANOS_TAIL (digits 7-12).
CREATE OR REPLACE FUNCTION ARCH.TS9(P_TS TIMESTAMP_NTZ(6), P_NANOS_TAIL INTEGER)
RETURNS TIMESTAMP_NTZ(9)
AS $$
    TIMESTAMPADD(NANOSECOND, FLOOR(COALESCE(P_NANOS_TAIL, 0) / 1000), P_TS::TIMESTAMP_NTZ(9))
$$;

-- A TIMESTAMP(9) as IS_ELIGIBLE compares it: PL/SQL compares against the package's TIMESTAMP (precision 6)
-- cutoff after rounding the fraction half-up to microseconds (23:59:59.9999995 -> next second).
CREATE OR REPLACE FUNCTION ARCH.PLSQL_TS6(P_TS TIMESTAMP_NTZ(9))
RETURNS TIMESTAMP_NTZ(9)
AS $$
    TIMESTAMPADD(NANOSECOND,
        IFF(MOD(DATE_PART(NANOSECOND, P_TS), 1000) >= 500, 1000, 0) - MOD(DATE_PART(NANOSECOND, P_TS), 1000), P_TS)
$$;

-- The distinct resolution outcomes of one code across the tenant's namespaces (0 = not in RETNPLCY).
CREATE OR REPLACE FUNCTION ARCH.POLICY_LOOKUP(P_CODE VARCHAR)
RETURNS ARRAY
AS $$
    SELECT ARRAY_UNIQUE_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
               'STATUS', r.STATUS, 'SOR_CODE', r.SOR_CODE, 'RETENTION_YEARS', r.RETENTION_YEARS,
               'DISPOSITION_ACTION', r.DISPOSITION_ACTION, 'IN_CLOSED_SCHEDULE', r.IN_CLOSED_SCHEDULE,
               'UNKNOWN_CODE', r.UNKNOWN_CODE))
      FROM ARCH.V_POLICY_RESOLUTION r
     WHERE r.POLICY_KEY = RTRIM(RPAD(COALESCE(P_CODE, '    '), 4))
$$;

-- Raises the package error for a resolution outcome that is not RESOLVED (NULL outcome = code not in RETNPLCY).
CREATE OR REPLACE FUNCTION ARCH.RESOLUTION_ERROR(P_OUTCOME OBJECT, P_CODE VARCHAR)
RETURNS VARIANT
AS $$
    CASE P_OUTCOME:STATUS::VARCHAR
        WHEN 'CYCLE' THEN ARCH.RAISE_APPLICATION_ERROR(-20003,
            'RETENTION_PKG: successor chain from "' || COALESCE(P_CODE, '') || '" does not terminate')
        WHEN 'CONFLICT' THEN ARCH.RAISE_APPLICATION_ERROR(-20002,
            'RETENTION_PKG: policy code "' || RPAD(COALESCE(P_CODE, '    '), 4) || '" resolves differently across namespaces')
        ELSE ARCH.RAISE_APPLICATION_ERROR(-20002,
            'RETENTION_PKG: unknown policy code "'
            || COALESCE(P_OUTCOME:UNKNOWN_CODE::VARCHAR, RPAD(COALESCE(P_CODE, '    '), 4)) || '"')
    END
$$;

-- The RESOLVED outcome of a code, or the package error.
CREATE OR REPLACE FUNCTION ARCH.RESOLVED_POLICY(P_CODE VARCHAR)
RETURNS OBJECT
AS $$
    CASE
        WHEN ARRAY_SIZE(ARCH.POLICY_LOOKUP(P_CODE)) > 1
            THEN ARCH.RESOLUTION_ERROR(OBJECT_CONSTRUCT('STATUS', 'CONFLICT'), P_CODE)::OBJECT
        WHEN ARCH.POLICY_LOOKUP(P_CODE)[0]:STATUS::VARCHAR = 'RESOLVED'
            THEN ARCH.POLICY_LOOKUP(P_CODE)[0]::OBJECT
        ELSE ARCH.RESOLUTION_ERROR(ARCH.POLICY_LOOKUP(P_CODE)[0]::OBJECT, P_CODE)::OBJECT
    END
$$;

-- RESOLVE_CLASS(p_code) RETURN CHAR: system-of-record class (F07R -> FIN7), -20002 unknown, -20003 > 8 hops.
CREATE OR REPLACE FUNCTION ARCH.RESOLVE_CLASS(P_CODE VARCHAR)
RETURNS CHAR(4)
AS $$
    ARCH.RESOLVED_POLICY(P_CODE):SOR_CODE::VARCHAR
$$;

-- RETENTION_YEARS(p_code) RETURN NUMBER: years of the resolved class.
CREATE OR REPLACE FUNCTION ARCH.RETENTION_YEARS(P_CODE VARCHAR)
RETURNS NUMBER(5, 0)
AS $$
    ARCH.RESOLVED_POLICY(P_CODE):RETENTION_YEARS::NUMBER(5, 0)
$$;

-- CUTOFF_TS(p_as_of DEFAULT DATE '2026-01-01') RETURN TIMESTAMP: ADD_MONTHS(TRUNC(as_of, 'YYYY'), -84).
CREATE OR REPLACE FUNCTION ARCH.CUTOFF_TS(P_AS_OF DATE DEFAULT '2026-01-01'::DATE)
RETURNS TIMESTAMP_NTZ(9)
AS $$
    ADD_MONTHS(DATE_TRUNC('YEAR', P_AS_OF), -84)::TIMESTAMP_NTZ(9)
$$;

-- IN_CLOSED_SCHEDULE(p_code) RETURN NUMBER: 1 iff the resolved class is in g_closed_schedule.
CREATE OR REPLACE FUNCTION ARCH.IN_CLOSED_SCHEDULE(P_CODE VARCHAR)
RETURNS NUMBER(1, 0)
AS $$
    ARCH.RESOLVED_POLICY(P_CODE):IN_CLOSED_SCHEDULE::NUMBER(1, 0)
$$;

-- IS_ELIGIBLE(p_code, p_last_access, p_legal_hold, p_as_of): the hold wins before the code is even resolved.
CREATE OR REPLACE FUNCTION ARCH.IS_ELIGIBLE(
    P_CODE VARCHAR, P_LAST_ACCESS TIMESTAMP_NTZ(9), P_LEGAL_HOLD VARCHAR, P_AS_OF DATE DEFAULT '2026-01-01'::DATE)
RETURNS NUMBER(1, 0)
AS $$
    CASE
        WHEN COALESCE(P_LEGAL_HOLD, 'N') = 'Y' THEN 0
        WHEN ARCH.IN_CLOSED_SCHEDULE(P_CODE) <> 1 THEN 0
        WHEN ARCH.PLSQL_TS6(P_LAST_ACCESS) < ARCH.CUTOFF_TS(P_AS_OF) THEN 1
        ELSE 0
    END
$$;

-- Same month/day, year + years; 29 February -> 28 February when the target year is not a leap year (the
-- package's ORA-01839 handler). Not ADD_MONTHS/DATEADD, which snap month ends differently.
CREATE OR REPLACE FUNCTION ARCH.ADD_RETENTION_YEARS(P_TS TIMESTAMP_NTZ(9), P_YEARS NUMBER)
RETURNS DATE
AS $$
    DATE_FROM_PARTS(
        YEAR(P_TS) + P_YEARS,
        MONTH(P_TS),
        IFF(MONTH(P_TS) = 2 AND DAY(P_TS) = 29
            AND NOT ((MOD(YEAR(P_TS) + P_YEARS, 4) = 0 AND MOD(YEAR(P_TS) + P_YEARS, 100) <> 0)
                     OR MOD(YEAR(P_TS) + P_YEARS, 400) = 0),
            28, DAY(P_TS)))
$$;

-- DISPOSITION_DATE(p_last_access, p_code) RETURN DATE.
CREATE OR REPLACE FUNCTION ARCH.DISPOSITION_DATE(P_LAST_ACCESS TIMESTAMP_NTZ(9), P_CODE VARCHAR)
RETURNS DATE
AS $$
    CASE WHEN ARCH.RETENTION_YEARS(P_CODE) IS NOT NULL
         THEN ARCH.ADD_RETENTION_YEARS(P_LAST_ACCESS, ARCH.RETENTION_YEARS(P_CODE)) END
$$;

-- NEXT_REVIEW_DATE(p_last_access, p_code) RETURN DATE: REVW classes only, disposition date + 6 months
-- (ADD_MONTHS: Snowflake snaps month ends exactly like Oracle, 2021-02-28 -> 2021-08-31).
CREATE OR REPLACE FUNCTION ARCH.NEXT_REVIEW_DATE(P_LAST_ACCESS TIMESTAMP_NTZ(9), P_CODE VARCHAR)
RETURNS DATE
AS $$
    IFF(ARCH.RESOLVED_POLICY(P_CODE):DISPOSITION_ACTION::VARCHAR <> 'REVW', NULL,
        ADD_MONTHS(ARCH.DISPOSITION_DATE(P_LAST_ACCESS, P_CODE), 6))
$$;

-- DISPOSITION_DT_TEXT(p_raw RAW) RETURN VARCHAR2: 8 EBCDIC cp037 digits (F0-F9) -> 'YYYYMMDD'; NULL, empty
-- (Oracle's empty RAW is NULL) and LOW-VALUES x'0000000000000000' -> NULL; anything else -20004. More than 8 bytes
-- overflow the package's VARCHAR2(8) buffer before the check (ORA-06502), reproduced with that code.
CREATE OR REPLACE FUNCTION ARCH.DISPOSITION_DT_TEXT(P_RAW BINARY)
RETURNS VARCHAR(8)
AS $$
    CASE
        WHEN P_RAW IS NULL OR LENGTH(P_RAW) = 0 OR P_RAW = TO_BINARY('0000000000000000', 'HEX') THEN NULL
        WHEN LENGTH(P_RAW) > 8 THEN ARCH.RAISE_APPLICATION_ERROR(-6502,
            'PL/SQL: value or conversion error: character string buffer too small')::VARCHAR
        WHEN REGEXP_LIKE(HEX_ENCODE(P_RAW), '(F[0-9]){8}') THEN REGEXP_REPLACE(HEX_ENCODE(P_RAW), 'F([0-9])', '\\1')
        ELSE ARCH.RAISE_APPLICATION_ERROR(-20004,
            'RETENTION_PKG: DISPOSITION_DT ' || HEX_ENCODE(P_RAW) || ' is not EBCDIC YYYYMMDD')::VARCHAR
    END
$$;

-- FILEAUD.DISPOSITION_CODE from resolved attributes: 40 hold, 90 permanent, 00 not yet due, 20 review, 10 destroy.
CREATE OR REPLACE FUNCTION ARCH.DISPOSITION_CODE_OF(
    P_LEGAL_HOLD VARCHAR, P_ACTION VARCHAR, P_DISPOSITION_DUE DATE, P_AS_OF DATE)
RETURNS CHAR(2)
AS $$
    CASE
        WHEN COALESCE(P_LEGAL_HOLD, 'N') = 'Y' THEN '40'
        WHEN RTRIM(P_ACTION) = 'PERM' THEN '90'
        WHEN P_DISPOSITION_DUE > P_AS_OF THEN '00'
        WHEN RTRIM(P_ACTION) = 'REVW' THEN '20'
        WHEN RTRIM(P_ACTION) = 'DEST' THEN '10'
        ELSE '00'
    END
$$;

-- DISPOSITION_CODE(p_code, p_last_access, p_legal_hold, p_as_of) RETURN CHAR: hold first, before resolution.
CREATE OR REPLACE FUNCTION ARCH.DISPOSITION_CODE(
    P_CODE VARCHAR, P_LAST_ACCESS TIMESTAMP_NTZ(9), P_LEGAL_HOLD VARCHAR, P_AS_OF DATE DEFAULT '2026-01-01'::DATE)
RETURNS CHAR(2)
AS $$
    CASE
        WHEN COALESCE(P_LEGAL_HOLD, 'N') = 'Y' THEN '40'
        ELSE ARCH.DISPOSITION_CODE_OF(
            P_LEGAL_HOLD,
            ARCH.RESOLVED_POLICY(P_CODE):DISPOSITION_ACTION::VARCHAR,
            IFF(ARCH.RESOLVED_POLICY(P_CODE):DISPOSITION_ACTION::VARCHAR = 'PERM', NULL,
                ARCH.DISPOSITION_DATE(P_LAST_ACCESS, P_CODE)),
            P_AS_OF)
    END
$$;
