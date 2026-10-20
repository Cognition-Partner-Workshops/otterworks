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
    -- DBMS_SQL binds :as_of by name, so a predicate may use it any number
    -- of times.
    FUNCTION run_sql (p_sql IN VARCHAR2, p_as_of IN DATE, p_count IN BOOLEAN) RETURN NUMBER IS
        l_cur  INTEGER := DBMS_SQL.OPEN_CURSOR;
        l_n    NUMBER;
        l_rows INTEGER;
    BEGIN
        DBMS_SQL.PARSE(l_cur, p_sql, DBMS_SQL.NATIVE);
        IF INSTR(LOWER(p_sql), ':as_of') > 0 THEN
            DBMS_SQL.BIND_VARIABLE(l_cur, ':as_of', p_as_of);
        END IF;
        IF p_count THEN
            DBMS_SQL.DEFINE_COLUMN(l_cur, 1, l_n);
            l_rows := DBMS_SQL.EXECUTE_AND_FETCH(l_cur);
            DBMS_SQL.COLUMN_VALUE(l_cur, 1, l_n);
        ELSE
            l_n := DBMS_SQL.EXECUTE(l_cur);
        END IF;
        DBMS_SQL.CLOSE_CURSOR(l_cur);
        RETURN l_n;
    EXCEPTION
        WHEN OTHERS THEN
            IF DBMS_SQL.IS_OPEN(l_cur) THEN
                DBMS_SQL.CLOSE_CURSOR(l_cur);
            END IF;
            RAISE;
    END run_sql;

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
    BEGIN
        l_matched := run_sql('SELECT COUNT(*) FROM "' || l_table || '" WHERE ' || p_predicate, p_as_of, TRUE);

        IF NOT p_dry_run AND l_matched > 0 THEN
            audit_purge_gate.open_gate;
            BEGIN
                l_purged := run_sql('DELETE FROM "' || l_table || '" WHERE ' || p_predicate, p_as_of, FALSE);
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
