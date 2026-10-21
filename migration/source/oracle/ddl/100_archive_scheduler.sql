-- Nightly disposition snapshot: DBMS_SCHEDULER job owned by ARCHIVE that materialises
-- RETENTION_PKG.CLASS_TOTALS into ARCHIVE.CLASS_TOTAL_SNAP at 02:00. Registered DISABLED in the
-- stand-in so the estate stays byte-identical between deploys; the production schedule is in the
-- job's comment and can be enabled with DBMS_SCHEDULER.ENABLE('ARCHIVE.NIGHTLY_DISPOSITION').
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;

BEGIN
    DBMS_SCHEDULER.CREATE_JOB(
        job_name        => 'ARCHIVE.NIGHTLY_DISPOSITION',
        job_type        => 'PLSQL_BLOCK',
        job_action      => 'BEGIN ARCHIVE.RETENTION_PKG.SNAPSHOT_CLASS_TOTALS(TRUNC(SYSDATE)); END;',
        start_date      => SYSTIMESTAMP,
        repeat_interval => 'FREQ=DAILY; BYHOUR=2; BYMINUTE=0; BYSECOND=0',
        enabled         => FALSE,
        auto_drop       => FALSE,
        comments        => 'Legacy nightly class-totals snapshot (prod: enabled, 02:00 site time).');
    DBMS_SCHEDULER.SET_ATTRIBUTE('ARCHIVE.NIGHTLY_DISPOSITION', 'max_failures', 3);
    DBMS_SCHEDULER.SET_ATTRIBUTE('ARCHIVE.NIGHTLY_DISPOSITION', 'restartable', TRUE);
END;
/
