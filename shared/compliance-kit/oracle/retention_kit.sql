-- compliance-kit / Oracle: retention purge pattern.
-- retention_kit.purge counts (dry run) or deletes the rows of one table that
-- a retention rule selects, and writes one RETENTION_RUN row either way, so
-- the purge leaves its own evidence: who ran it, when, under which policy,
-- with which predicate, how many rows matched and how many went.
-- The predicate is code written by the schema owner in a policy package,
-- never user input. Install after audit_kit.sql.
WHENEVER SQLERROR EXIT SQL.SQLCODE

CREATE TABLE retention_run (
    run_id       NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name  VARCHAR2(128) NOT NULL,
    table_name   VARCHAR2(128) NOT NULL,
    predicate    VARCHAR2(4000) NOT NULL,
    as_of        DATE          NOT NULL,
    dry_run      CHAR(1)       NOT NULL CONSTRAINT ck_rr_dry CHECK (dry_run IN ('Y', 'N')),
    rows_matched NUMBER        NOT NULL,
    rows_purged  NUMBER        NOT NULL,
    run_by       VARCHAR2(128) DEFAULT SYS_CONTEXT('USERENV', 'SESSION_USER') NOT NULL,
    run_at       TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE OR REPLACE PACKAGE retention_kit AS
    -- p_predicate may reference the bind :as_of (DATE). Returns rows matched.
    FUNCTION purge (
        p_policy_name IN VARCHAR2,
        p_table_name  IN VARCHAR2,
        p_predicate   IN VARCHAR2,
        p_as_of       IN DATE,
        p_dry_run     IN BOOLEAN DEFAULT TRUE
    ) RETURN NUMBER;
END retention_kit;
/

CREATE OR REPLACE PACKAGE BODY retention_kit AS
    FUNCTION purge (
        p_policy_name IN VARCHAR2,
        p_table_name  IN VARCHAR2,
        p_predicate   IN VARCHAR2,
        p_as_of       IN DATE,
        p_dry_run     IN BOOLEAN DEFAULT TRUE
    ) RETURN NUMBER IS
        l_table   VARCHAR2(128) := UPPER(DBMS_ASSERT.SIMPLE_SQL_NAME(p_table_name));
        l_matched NUMBER;
        l_purged  NUMBER := 0;
        l_uses_as_of BOOLEAN := INSTR(LOWER(p_predicate), ':as_of') > 0;
    BEGIN
        IF l_uses_as_of THEN
            EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM "' || l_table || '" WHERE ' || p_predicate
                INTO l_matched USING p_as_of;
        ELSE
            EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM "' || l_table || '" WHERE ' || p_predicate
                INTO l_matched;
        END IF;

        IF NOT p_dry_run AND l_matched > 0 THEN
            audit_purge_gate.open_gate;
            BEGIN
                IF l_uses_as_of THEN
                    EXECUTE IMMEDIATE 'DELETE FROM "' || l_table || '" WHERE ' || p_predicate USING p_as_of;
                ELSE
                    EXECUTE IMMEDIATE 'DELETE FROM "' || l_table || '" WHERE ' || p_predicate;
                END IF;
                l_purged := SQL%ROWCOUNT;
                audit_purge_gate.close_gate;
            EXCEPTION
                WHEN OTHERS THEN
                    audit_purge_gate.close_gate;
                    ROLLBACK;
                    RAISE;
            END;
        END IF;

        INSERT INTO retention_run (policy_name, table_name, predicate, as_of, dry_run, rows_matched, rows_purged)
        VALUES (p_policy_name, l_table, p_predicate, p_as_of,
                CASE WHEN p_dry_run THEN 'Y' ELSE 'N' END, l_matched, l_purged);
        COMMIT;
        RETURN l_matched;
    END purge;
END retention_kit;
/

EXIT;
