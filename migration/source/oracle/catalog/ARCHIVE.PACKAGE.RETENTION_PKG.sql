
  CREATE OR REPLACE EDITIONABLE PACKAGE "ARCHIVE"."RETENTION_PKG" AUTHID DEFINER AS
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