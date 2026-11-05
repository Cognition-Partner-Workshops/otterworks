-- ARCHIVE.RETENTION_PKG: the records-retention business rules of the legacy archive, as the estate
-- team left them. Installed on first start after the tables (010-050) and before the views (080),
-- trigger (090), scheduler job (100) and grants (110) that depend on it.
--
-- The migration engine (migration/job) re-implements the SELECTION rules of this package in the
-- manifest (selection_sets.closed-7y, last_access_before, class_totals.source_class_resolution).
-- Porting the package itself is the engineering work: it leans on Oracle-only behaviour on purpose
-- (CHAR blank-padded comparison, NVL/DECODE, SYS_REFCURSOR, ROWNUM batching, PRAGMA AUTONOMOUS_TRANSACTION,
-- RAISE_APPLICATION_ERROR codes, UTL_RAW EBCDIC conversion, exception-driven leap-day handling).
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;

-- Definer-rights package: ARCHIVE itself needs the MIGAUDIT object privileges (roles do not apply).
GRANT INSERT ON MIGAUDIT.PURGE_AUDIT TO ARCHIVE;
GRANT INSERT ON MIGAUDIT.PURGE_LOG   TO ARCHIVE;
GRANT CREATE JOB TO ARCHIVE;

-- Successor lineage of every policy code: SOR_CODE is the active code a retired code rolls up to.
-- Hierarchical query over RETNPLCY.SUCCESSOR_CODE (blank = active, terminates the chain).
CREATE OR REPLACE VIEW ARCHIVE.V_POLICY_LINEAGE AS
SELECT CONNECT_BY_ROOT POLICY_CODE                                  AS POLICY_CODE,
       POLICY_CODE                                                  AS SOR_CODE,
       LEVEL - 1                                                    AS HOPS,
       LTRIM(SYS_CONNECT_BY_PATH(RTRIM(POLICY_CODE), '>'), '>')     AS LINEAGE,
       CASE WHEN RTRIM(POLICY_CODE) IN ('FIN7', 'LGL7', 'HRS7', 'TAX7', 'AUD7') THEN 1 ELSE 0 END
                                                                    AS IN_CLOSED_SCHEDULE
  FROM ARCHIVE.RETNPLCY
 WHERE CONNECT_BY_ISLEAF = 1
 START WITH POLICY_CODE IS NOT NULL
 CONNECT BY NOCYCLE PRIOR SUCCESSOR_CODE = POLICY_CODE;

CREATE TABLE ARCHIVE.CLASS_TOTAL_SNAP (
    SNAP_TS             TIMESTAMP(9)    DEFAULT SYSTIMESTAMP NOT NULL,
    AS_OF_DT            DATE            NOT NULL,
    RETENTION_CLASS     CHAR(4)         NOT NULL,
    DOC_COUNT           NUMBER(12)      NOT NULL,
    CHARGE_TOTAL        NUMBER(31,8)    NOT NULL,
    CONSTRAINT PK_CLASS_TOTAL_SNAP PRIMARY KEY (SNAP_TS, RETENTION_CLASS)
);

CREATE OR REPLACE PACKAGE ARCHIVE.RETENTION_PKG AUTHID DEFINER AS
    -- Disposition cycle the rules are evaluated against when no AS-OF date is given (the annual
    -- run of 1 January). CUTOFF = AS-OF truncated to the year, minus 84 months (7 years).
    c_default_as_of     CONSTANT DATE          := DATE '2026-01-01';
    c_closed_schedule   CONSTANT VARCHAR2(6)   := 'CLSD7Y';
    c_blank_code        CONSTANT CHAR(4)       := '    ';
    c_lowvalues_dt      CONSTANT RAW(8)        := HEXTORAW('0000000000000000');
    c_max_hops          CONSTANT PLS_INTEGER   := 8;

    -- Application error codes (RAISE_APPLICATION_ERROR): keep in sync with MIGRATION-NOTES.md.
    c_err_confirm       CONSTANT PLS_INTEGER   := -20001;  -- purge called without the confirmation phrase
    c_err_unknown_code  CONSTANT PLS_INTEGER   := -20002;  -- policy code not in RETNPLCY
    c_err_cycle         CONSTANT PLS_INTEGER   := -20003;  -- successor chain does not terminate
    c_err_bad_date      CONSTANT PLS_INTEGER   := -20004;  -- DISPOSITION_DT is neither digits nor low-values

    e_purge_not_confirmed EXCEPTION;
    PRAGMA EXCEPTION_INIT(e_purge_not_confirmed, -20001);

    -- System-of-record class: follow RETNPLCY.SUCCESSOR_CODE until an active code (blank successor).
    FUNCTION resolve_class(p_code IN VARCHAR2) RETURN CHAR;

    -- RETENTION_YEARS of the *resolved* class.
    FUNCTION retention_years(p_code IN VARCHAR2) RETURN NUMBER;

    -- First instant of the disposition window: rows last accessed before it are due.
    FUNCTION cutoff_ts(p_as_of IN DATE DEFAULT c_default_as_of) RETURN TIMESTAMP;

    -- Whether p_code belongs to the closed 7-year destruction schedule (after resolution).
    FUNCTION in_closed_schedule(p_code IN VARCHAR2) RETURN NUMBER;

    -- 1 when the row is due for destruction under the closed 7-year schedule as of p_as_of, else 0.
    FUNCTION is_eligible(
        p_code        IN VARCHAR2,
        p_last_access IN TIMESTAMP,
        p_legal_hold  IN VARCHAR2,
        p_as_of       IN DATE DEFAULT c_default_as_of) RETURN NUMBER;

    -- Calendar date the row leaves retention: LAST_ACCESS + RETENTION_YEARS, same month and day;
    -- 29 February of a leap year rolls to 28 February. (NOT ADD_MONTHS: that snaps month ends.)
    FUNCTION disposition_date(p_last_access IN TIMESTAMP, p_code IN VARCHAR2) RETURN DATE;

    -- Review date for REVW policies (9-year classes): disposition date + 6 months; NULL otherwise.
    FUNCTION next_review_date(p_last_access IN TIMESTAMP, p_code IN VARCHAR2) RETURN DATE;

    -- DOCARCH.DISPOSITION_DT is 8 EBCDIC (cp037) digits YYYYMMDD, or low-values for "not yet set".
    FUNCTION disposition_dt_text(p_raw IN RAW) RETURN VARCHAR2;

    -- FILEAUD.DISPOSITION_CODE: 00 pending, 10 destroy due, 20 review due, 40 legal hold, 90 permanent.
    FUNCTION disposition_code(
        p_code        IN VARCHAR2,
        p_last_access IN TIMESTAMP,
        p_legal_hold  IN VARCHAR2,
        p_as_of       IN DATE DEFAULT c_default_as_of) RETURN CHAR;

    -- Per system-of-record class over eligible DOCARCH rows: (RETENTION_CLASS, DOC_COUNT, CHARGE_TOTAL).
    FUNCTION class_totals(p_as_of IN DATE DEFAULT c_default_as_of) RETURN SYS_REFCURSOR;

    -- Nightly snapshot of class_totals into ARCHIVE.CLASS_TOTAL_SNAP (DBMS_SCHEDULER target).
    PROCEDURE snapshot_class_totals(p_as_of IN DATE DEFAULT c_default_as_of);

    -- Legacy destruction routine: audit row first, children before parent, one batch per call.
    -- Refuses to run unless p_confirm = 'DESTROY ELIGIBLE RECORDS'. Progress is logged through an
    -- autonomous transaction, so the log survives a rollback of the batch.
    PROCEDURE purge_eligible(
        p_run_id     IN  VARCHAR2,
        p_batch_rows IN  PLS_INTEGER DEFAULT 1000,
        p_confirm    IN  VARCHAR2    DEFAULT NULL,
        p_as_of      IN  DATE        DEFAULT c_default_as_of,
        p_purged     OUT NUMBER);
END RETENTION_PKG;
/

CREATE OR REPLACE PACKAGE BODY ARCHIVE.RETENTION_PKG AS
    TYPE t_flag_tab IS TABLE OF PLS_INTEGER INDEX BY VARCHAR2(4);
    g_closed_schedule t_flag_tab;   -- hard-coded membership; the schedule table never got built

    PROCEDURE log_purge(p_run_id IN VARCHAR2, p_severity IN VARCHAR2, p_message IN VARCHAR2) IS
        PRAGMA AUTONOMOUS_TRANSACTION;
    BEGIN
        INSERT INTO MIGAUDIT.PURGE_LOG (RUN_ID, SEVERITY, MESSAGE)
        VALUES (p_run_id, p_severity, SUBSTR(p_message, 1, 4000));
        COMMIT;
    END log_purge;

    FUNCTION resolve_class(p_code IN VARCHAR2) RETURN CHAR IS
        v_code      CHAR(4) := RPAD(NVL(p_code, c_blank_code), 4);
        v_successor CHAR(4);
        v_hops      PLS_INTEGER := 0;
    BEGIN
        LOOP
            BEGIN
                SELECT SUCCESSOR_CODE INTO v_successor
                  FROM ARCHIVE.RETNPLCY
                 WHERE POLICY_CODE = v_code;
            EXCEPTION
                WHEN NO_DATA_FOUND THEN
                    RAISE_APPLICATION_ERROR(c_err_unknown_code, 'RETENTION_PKG: unknown policy code "' || v_code || '"');
            END;
            -- CHAR semantics: a blank successor compares equal to '' padded, RTRIM makes it NULL.
            EXIT WHEN RTRIM(v_successor) IS NULL;
            v_hops := v_hops + 1;
            IF v_hops > c_max_hops THEN
                RAISE_APPLICATION_ERROR(c_err_cycle, 'RETENTION_PKG: successor chain from "' || p_code || '" does not terminate');
            END IF;
            v_code := v_successor;
        END LOOP;
        RETURN v_code;
    END resolve_class;

    FUNCTION retention_years(p_code IN VARCHAR2) RETURN NUMBER IS
        v_years NUMBER(5);
    BEGIN
        SELECT RETENTION_YEARS INTO v_years
          FROM ARCHIVE.RETNPLCY
         WHERE POLICY_CODE = resolve_class(p_code);
        RETURN v_years;
    END retention_years;

    FUNCTION cutoff_ts(p_as_of IN DATE DEFAULT c_default_as_of) RETURN TIMESTAMP IS
    BEGIN
        RETURN CAST(ADD_MONTHS(TRUNC(p_as_of, 'YYYY'), -84) AS TIMESTAMP);
    END cutoff_ts;

    FUNCTION in_closed_schedule(p_code IN VARCHAR2) RETURN NUMBER IS
    BEGIN
        RETURN CASE WHEN g_closed_schedule.EXISTS(RTRIM(resolve_class(p_code))) THEN 1 ELSE 0 END;
    END in_closed_schedule;

    FUNCTION is_eligible(
        p_code        IN VARCHAR2,
        p_last_access IN TIMESTAMP,
        p_legal_hold  IN VARCHAR2,
        p_as_of       IN DATE DEFAULT c_default_as_of) RETURN NUMBER IS
    BEGIN
        IF NVL(p_legal_hold, 'N') = 'Y' THEN
            RETURN 0;
        END IF;
        RETURN CASE WHEN in_closed_schedule(p_code) = 1
                     AND p_last_access < cutoff_ts(p_as_of)
                    THEN 1 ELSE 0 END;
    END is_eligible;

    FUNCTION disposition_date(p_last_access IN TIMESTAMP, p_code IN VARCHAR2) RETURN DATE IS
        v_years  NUMBER(5) := retention_years(p_code);
        v_target VARCHAR2(8);
        e_bad_day EXCEPTION;
        PRAGMA EXCEPTION_INIT(e_bad_day, -1839);   -- ORA-01839: date not valid for month specified
    BEGIN
        v_target := TO_CHAR(EXTRACT(YEAR FROM p_last_access) + v_years, 'FM0000') || TO_CHAR(p_last_access, 'MMDD');
        BEGIN
            RETURN TO_DATE(v_target, 'YYYYMMDD');
        EXCEPTION
            WHEN e_bad_day THEN
                RETURN TO_DATE(SUBSTR(v_target, 1, 4) || '0228', 'YYYYMMDD');
        END;
    END disposition_date;

    FUNCTION next_review_date(p_last_access IN TIMESTAMP, p_code IN VARCHAR2) RETURN DATE IS
        v_action CHAR(4);
    BEGIN
        SELECT DISPOSITION_ACTION INTO v_action
          FROM ARCHIVE.RETNPLCY
         WHERE POLICY_CODE = resolve_class(p_code);
        IF v_action <> 'REVW' THEN
            RETURN NULL;
        END IF;
        RETURN ADD_MONTHS(disposition_date(p_last_access, p_code), 6);
    END next_review_date;

    FUNCTION disposition_dt_text(p_raw IN RAW) RETURN VARCHAR2 IS
        v_text VARCHAR2(8);
    BEGIN
        IF p_raw IS NULL OR p_raw = c_lowvalues_dt THEN
            RETURN NULL;
        END IF;
        v_text := UTL_RAW.CAST_TO_VARCHAR2(
                      UTL_RAW.CONVERT(p_raw, 'AMERICAN_AMERICA.US7ASCII', 'AMERICAN_AMERICA.WE8EBCDIC37'));
        IF NOT REGEXP_LIKE(v_text, '^[0-9]{8}$') THEN
            RAISE_APPLICATION_ERROR(c_err_bad_date, 'RETENTION_PKG: DISPOSITION_DT ' || RAWTOHEX(p_raw) || ' is not EBCDIC YYYYMMDD');
        END IF;
        RETURN v_text;
    END disposition_dt_text;

    FUNCTION disposition_code(
        p_code        IN VARCHAR2,
        p_last_access IN TIMESTAMP,
        p_legal_hold  IN VARCHAR2,
        p_as_of       IN DATE DEFAULT c_default_as_of) RETURN CHAR IS
        v_action CHAR(4);
    BEGIN
        IF NVL(p_legal_hold, 'N') = 'Y' THEN
            RETURN '40';
        END IF;
        SELECT DISPOSITION_ACTION INTO v_action
          FROM ARCHIVE.RETNPLCY
         WHERE POLICY_CODE = resolve_class(p_code);
        IF v_action = 'PERM' THEN
            RETURN '90';
        END IF;
        IF disposition_date(p_last_access, p_code) > p_as_of THEN
            RETURN '00';
        END IF;
        RETURN CASE v_action WHEN 'REVW' THEN '20' WHEN 'DEST' THEN '10' ELSE '00' END;
    END disposition_code;

    FUNCTION class_totals(p_as_of IN DATE DEFAULT c_default_as_of) RETURN SYS_REFCURSOR IS
        v_cur SYS_REFCURSOR;
    BEGIN
        OPEN v_cur FOR
            SELECT l.SOR_CODE                          AS RETENTION_CLASS,
                   COUNT(*)                            AS DOC_COUNT,
                   ROUND(SUM(d.STORAGE_CHARGE), 8)     AS CHARGE_TOTAL
              FROM ARCHIVE.DOCARCH d
              JOIN ARCHIVE.V_POLICY_LINEAGE l ON l.POLICY_CODE = d.RETENTION_CLASS
             WHERE l.IN_CLOSED_SCHEDULE = 1
               AND d.LEGAL_HOLD_FLAG = 'N'
               AND d.LAST_ACCESS_TS < cutoff_ts(p_as_of)
             GROUP BY l.SOR_CODE
             ORDER BY l.SOR_CODE;
        RETURN v_cur;
    END class_totals;

    PROCEDURE snapshot_class_totals(p_as_of IN DATE DEFAULT c_default_as_of) IS
        v_cur   SYS_REFCURSOR := class_totals(p_as_of);
        v_class CHAR(4);
        v_count NUMBER;
        v_total NUMBER;
        v_snap  TIMESTAMP(9) := SYSTIMESTAMP;
    BEGIN
        LOOP
            FETCH v_cur INTO v_class, v_count, v_total;
            EXIT WHEN v_cur%NOTFOUND;
            INSERT INTO ARCHIVE.CLASS_TOTAL_SNAP (SNAP_TS, AS_OF_DT, RETENTION_CLASS, DOC_COUNT, CHARGE_TOTAL)
            VALUES (v_snap, p_as_of, v_class, v_count, v_total);
        END LOOP;
        CLOSE v_cur;
        COMMIT;
    END snapshot_class_totals;

    PROCEDURE purge_eligible(
        p_run_id     IN  VARCHAR2,
        p_batch_rows IN  PLS_INTEGER DEFAULT 1000,
        p_confirm    IN  VARCHAR2    DEFAULT NULL,
        p_as_of      IN  DATE        DEFAULT c_default_as_of,
        p_purged     OUT NUMBER) IS
        TYPE t_key_tab IS TABLE OF ARCHIVE.DOCARCH.ARCH_KEY%TYPE;
        v_keys   t_key_tab;
        v_cutoff TIMESTAMP := cutoff_ts(p_as_of);
    BEGIN
        p_purged := 0;
        IF p_confirm IS NULL OR p_confirm <> 'DESTROY ELIGIBLE RECORDS' THEN
            RAISE_APPLICATION_ERROR(c_err_confirm, 'RETENTION_PKG.PURGE_ELIGIBLE: confirmation phrase missing');
        END IF;
        log_purge(p_run_id, 'INFO', 'batch start: as_of=' || TO_CHAR(p_as_of, 'YYYY-MM-DD') || ' rows=' || p_batch_rows);

        SELECT d.ARCH_KEY BULK COLLECT INTO v_keys
          FROM ARCHIVE.DOCARCH d
          JOIN ARCHIVE.V_POLICY_LINEAGE l ON l.POLICY_CODE = d.RETENTION_CLASS
         WHERE l.IN_CLOSED_SCHEDULE = 1
           AND d.LEGAL_HOLD_FLAG = 'N'
           AND d.LAST_ACCESS_TS < v_cutoff
           AND ROWNUM <= p_batch_rows
         ORDER BY d.ARCH_KEY;

        FOR i IN 1 .. v_keys.COUNT LOOP
            INSERT INTO MIGAUDIT.PURGE_AUDIT (RUN_ID, TABLE_NAME, SOURCE_KEY)
                SELECT p_run_id, 'FILEAUD', AUDIT_KEY FROM ARCHIVE.FILEAUD WHERE ARCH_KEY = v_keys(i);
            DELETE FROM ARCHIVE.FILEAUD WHERE ARCH_KEY = v_keys(i);
            INSERT INTO MIGAUDIT.PURGE_AUDIT (RUN_ID, TABLE_NAME, SOURCE_KEY)
                VALUES (p_run_id, 'DOCARCH', v_keys(i));
            DELETE FROM ARCHIVE.DOCARCH WHERE ARCH_KEY = v_keys(i);
            p_purged := p_purged + 1;
        END LOOP;
        log_purge(p_run_id, 'INFO', 'batch end: purged=' || p_purged);
    EXCEPTION
        WHEN e_purge_not_confirmed THEN
            RAISE;
        WHEN OTHERS THEN
            log_purge(p_run_id, 'ERROR', 'batch failed after ' || p_purged || ' rows: ' || SQLERRM);
            RAISE;
    END purge_eligible;

BEGIN
    g_closed_schedule('FIN7') := 1;
    g_closed_schedule('LGL7') := 1;
    g_closed_schedule('HRS7') := 1;
    g_closed_schedule('TAX7') := 1;
    g_closed_schedule('AUD7') := 1;
END RETENTION_PKG;
/

SHOW ERRORS PACKAGE ARCHIVE.RETENTION_PKG
SHOW ERRORS PACKAGE BODY ARCHIVE.RETENTION_PKG

-- A package that compiled with errors is only a warning to SQL*Plus; make it fail the first start.
DECLARE
    v_errors PLS_INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_errors
      FROM DBA_ERRORS
     WHERE OWNER = 'ARCHIVE' AND NAME = 'RETENTION_PKG' AND ATTRIBUTE = 'ERROR';
    IF v_errors > 0 THEN
        RAISE_APPLICATION_ERROR(-20000, 'ARCHIVE.RETENTION_PKG has ' || v_errors || ' compilation error(s)');
    END IF;
END;
/
