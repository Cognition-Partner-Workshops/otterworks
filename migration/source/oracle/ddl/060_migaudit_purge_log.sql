-- MIGAUDIT.PURGE_LOG: free-text progress log of the legacy destruction routine
-- (ARCHIVE.RETENTION_PKG.PURGE_ELIGIBLE). Written through an autonomous transaction, so entries
-- survive a rollback of the batch that produced them. Never purged, never migrated.
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SESSION SET CONTAINER = FREEPDB1;

CREATE TABLE MIGAUDIT.PURGE_LOG (
    LOG_ID              NUMBER          GENERATED ALWAYS AS IDENTITY,
    RUN_ID              VARCHAR2(64)    NOT NULL,
    LOGGED_AT           TIMESTAMP(9)    DEFAULT SYSTIMESTAMP NOT NULL,
    SEVERITY            VARCHAR2(5)     NOT NULL,
    MESSAGE             VARCHAR2(4000)  NOT NULL,
    CONSTRAINT PK_PURGE_LOG PRIMARY KEY (LOG_ID),
    CONSTRAINT CK_PURGE_LOG_SEV CHECK (SEVERITY IN ('INFO', 'WARN', 'ERROR'))
);
