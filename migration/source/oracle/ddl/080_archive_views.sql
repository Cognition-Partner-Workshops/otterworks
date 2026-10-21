-- Reporting views the retention team runs against the archive. V_POLICY_LINEAGE (070) is the
-- set-based lineage; the views below call RETENTION_PKG per row (a PL/SQL context switch per row -
-- fine for the nightly report, not for a bulk engine).
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;

-- Rows due for destruction in the current cycle, with the derived dates the report shows.
CREATE OR REPLACE VIEW ARCHIVE.V_ELIGIBLE_DOCS AS
SELECT d.ARCH_KEY,
       d.DOC_ID,
       d.VERSION_NO,
       d.RETENTION_CLASS,
       ARCHIVE.RETENTION_PKG.RESOLVE_CLASS(d.RETENTION_CLASS)                              AS SOR_CLASS,
       d.LAST_ACCESS_TS,
       d.STORAGE_CHARGE,
       d.BYTE_SIZE,
       d.LEGAL_HOLD_FLAG,
       ARCHIVE.RETENTION_PKG.DISPOSITION_DATE(d.LAST_ACCESS_TS, d.RETENTION_CLASS)         AS DISPOSITION_DUE,
       ARCHIVE.RETENTION_PKG.DISPOSITION_DT_TEXT(d.DISPOSITION_DT)                         AS DISPOSITION_DT_STORED,
       ARCHIVE.RETENTION_PKG.DISPOSITION_CODE(d.RETENTION_CLASS, d.LAST_ACCESS_TS, d.LEGAL_HOLD_FLAG)
                                                                                           AS DISPOSITION_CODE
  FROM ARCHIVE.DOCARCH d
 WHERE ARCHIVE.RETENTION_PKG.IS_ELIGIBLE(d.RETENTION_CLASS, d.LAST_ACCESS_TS, d.LEGAL_HOLD_FLAG) = 1;

-- Per system-of-record class over the eligible population (same numbers as RETENTION_PKG.CLASS_TOTALS).
CREATE OR REPLACE VIEW ARCHIVE.V_CLASS_TOTALS AS
SELECT l.SOR_CODE                          AS RETENTION_CLASS,
       COUNT(*)                            AS DOC_COUNT,
       ROUND(SUM(d.STORAGE_CHARGE), 8)     AS CHARGE_TOTAL,
       MIN(d.LAST_ACCESS_TS)               AS OLDEST_ACCESS_TS,
       MAX(d.LAST_ACCESS_TS)               AS NEWEST_ACCESS_TS
  FROM ARCHIVE.DOCARCH d
  JOIN ARCHIVE.V_POLICY_LINEAGE l ON l.POLICY_CODE = d.RETENTION_CLASS
 WHERE l.IN_CLOSED_SCHEDULE = 1
   AND d.LEGAL_HOLD_FLAG = 'N'
   AND d.LAST_ACCESS_TS < ARCHIVE.RETENTION_PKG.CUTOFF_TS()
 GROUP BY l.SOR_CODE;

-- Documents under legal hold, with the last HOLD event that put them there (if any survived).
CREATE OR REPLACE VIEW ARCHIVE.V_LEGAL_HOLDS AS
SELECT d.ARCH_KEY,
       d.DOC_ID,
       d.RETENTION_CLASS,
       d.LAST_ACCESS_TS,
       NVL(UTL_RAW.CAST_TO_VARCHAR2(UTL_RAW.CONVERT(d.OWNER_NAME,
               'AMERICAN_AMERICA.WE8ISO8859P1', 'AMERICAN_AMERICA.WE8EBCDIC37')), '?')  AS OWNER_NAME,
       (SELECT MAX(f.EVENT_TS) FROM ARCHIVE.FILEAUD f
         WHERE f.ARCH_KEY = d.ARCH_KEY AND f.EVENT_TYPE = 'HOLD')                        AS LAST_HOLD_TS,
       (SELECT COUNT(*) FROM ARCHIVE.FILEAUD f WHERE f.ARCH_KEY = d.ARCH_KEY)            AS AUDIT_EVENTS
  FROM ARCHIVE.DOCARCH d
 WHERE d.LEGAL_HOLD_FLAG = 'Y';
