-- compliance-kit / Oracle: row-change audit trail.
-- Install into the schema that owns the audited tables, then call
-- audit_kit.install_row_audit('<TABLE>', '<KEY_COL>[,<KEY_COL>...]') per table
-- and audit_kit.protect_append_only('<TABLE>') for every log table.
--
-- Every INSERT, UPDATE and DELETE on an audited table writes one row to
-- AUDIT_ROW_CHANGE in the same transaction (a rolled back change leaves no
-- row), whether it came through a package or a direct statement. Each row
-- carries the authenticated session identity (SESSION_USER, OS user, host,
-- program, client identifier), the program unit that issued the DML, the
-- application actor when that unit declared one with set_actor, the time,
-- and the before and after values as JSON.
WHENEVER SQLERROR EXIT SQL.SQLCODE

CREATE TABLE audit_row_change (
    change_id         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name        VARCHAR2(128) NOT NULL,
    row_key           VARCHAR2(400) NOT NULL,
    operation         VARCHAR2(8)   NOT NULL
                      CONSTRAINT ck_arc_operation CHECK (operation IN ('BASELINE', 'INSERT', 'UPDATE', 'DELETE')),
    changed_at        TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    app_actor         VARCHAR2(128),
    db_user           VARCHAR2(128) NOT NULL,
    os_user           VARCHAR2(128),
    client_host       VARCHAR2(256),
    client_program    VARCHAR2(128),
    client_identifier VARCHAR2(128),
    via_program       VARCHAR2(256) NOT NULL,
    txn_id            VARCHAR2(64),
    old_values        CLOB CONSTRAINT ck_arc_old_json CHECK (old_values IS JSON),
    new_values        CLOB CONSTRAINT ck_arc_new_json CHECK (new_values IS JSON)
);

CREATE INDEX ix_arc_table_key ON audit_row_change (table_name, row_key, change_id);
CREATE INDEX ix_arc_changed_at ON audit_row_change (changed_at);

-- Deletes from a protected log are allowed only while retention_kit holds the
-- gate open; nothing else can open it.
CREATE OR REPLACE PACKAGE audit_purge_gate AS
    PROCEDURE open_gate  ACCESSIBLE BY (PACKAGE retention_kit);
    PROCEDURE close_gate ACCESSIBLE BY (PACKAGE retention_kit);
    FUNCTION is_open RETURN BOOLEAN;
END audit_purge_gate;
/

CREATE OR REPLACE PACKAGE BODY audit_purge_gate AS
    g_open BOOLEAN := FALSE;

    PROCEDURE open_gate ACCESSIBLE BY (PACKAGE retention_kit) IS
    BEGIN
        g_open := TRUE;
    END open_gate;

    PROCEDURE close_gate ACCESSIBLE BY (PACKAGE retention_kit) IS
    BEGIN
        g_open := FALSE;
    END close_gate;

    FUNCTION is_open RETURN BOOLEAN IS
    BEGIN
        RETURN g_open;
    END is_open;
END audit_purge_gate;
/

CREATE OR REPLACE PACKAGE audit_kit AS
    -- Declare the application actor for the DML the calling program unit
    -- issues next. The actor is attached only to changes issued by that same
    -- unit, so a stale value never leaks onto a later direct statement.
    PROCEDURE set_actor (p_actor IN VARCHAR2);
    PROCEDURE clear_actor;

    -- Called by the generated triggers.
    PROCEDURE record_change (
        p_table_name IN VARCHAR2,
        p_row_key    IN VARCHAR2,
        p_operation  IN VARCHAR2,
        p_old_values IN CLOB,
        p_new_values IN CLOB
    );

    -- Generate TRG_AUD_<table> over every non-LOB column and, when
    -- p_baseline is TRUE, write one BASELINE row per existing row so every
    -- key has a first entry.
    PROCEDURE install_row_audit (
        p_table_name  IN VARCHAR2,
        p_key_columns IN VARCHAR2,
        p_baseline    IN BOOLEAN DEFAULT TRUE
    );

    -- Generate TRG_APPEND_ONLY_<table>: UPDATE is always refused and DELETE
    -- is refused unless retention_kit is purging (ORA-20901).
    PROCEDURE protect_append_only (p_table_name IN VARCHAR2);
END audit_kit;
/

CREATE OR REPLACE PACKAGE BODY audit_kit AS
    g_actor      VARCHAR2(128);
    g_actor_unit VARCHAR2(256);

    -- Program unit p_depth frames above the caller of unit_at (1 = caller),
    -- or 'SQL' when the stack ends first: the DML came straight from a client.
    FUNCTION unit_at (p_depth IN PLS_INTEGER) RETURN VARCHAR2 IS
        l_depth PLS_INTEGER := p_depth + 1;
    BEGIN
        IF l_depth > UTL_CALL_STACK.DYNAMIC_DEPTH THEN
            RETURN 'SQL';
        END IF;
        RETURN UTL_CALL_STACK.CONCATENATE_SUBPROGRAM(UTL_CALL_STACK.SUBPROGRAM(l_depth));
    END unit_at;

    -- The program unit that issued the DML the current trigger is firing
    -- for: the first frame below the trigger that is not the SQL statement
    -- itself. 'SQL' when there is none (the statement came from a client),
    -- 'ANONYMOUS BLOCK' for an unnamed PL/SQL block.
    FUNCTION issuing_unit RETURN VARCHAR2 IS
        l_after_trigger BOOLEAN := FALSE;
    BEGIN
        FOR i IN 1 .. UTL_CALL_STACK.DYNAMIC_DEPTH LOOP
            IF l_after_trigger AND UTL_CALL_STACK.UNIT_TYPE(i) <> 'SQL' THEN
                IF UTL_CALL_STACK.UNIT_TYPE(i) = 'ANONYMOUS BLOCK' THEN
                    RETURN 'ANONYMOUS BLOCK';
                END IF;
                RETURN UTL_CALL_STACK.CONCATENATE_SUBPROGRAM(UTL_CALL_STACK.SUBPROGRAM(i));
            END IF;
            IF UTL_CALL_STACK.UNIT_TYPE(i) = 'TRIGGER' THEN
                l_after_trigger := TRUE;
            END IF;
        END LOOP;
        RETURN 'SQL';
    END issuing_unit;

    PROCEDURE set_actor (p_actor IN VARCHAR2) IS
    BEGIN
        g_actor := p_actor;
        g_actor_unit := unit_at(2);
    END set_actor;

    PROCEDURE clear_actor IS
    BEGIN
        g_actor := NULL;
        g_actor_unit := NULL;
    END clear_actor;

    PROCEDURE record_change (
        p_table_name IN VARCHAR2,
        p_row_key    IN VARCHAR2,
        p_operation  IN VARCHAR2,
        p_old_values IN CLOB,
        p_new_values IN CLOB
    ) IS
        l_via VARCHAR2(256) := issuing_unit;
    BEGIN
        INSERT INTO audit_row_change (
            table_name, row_key, operation, app_actor, db_user, os_user, client_host,
            client_program, client_identifier, via_program, txn_id, old_values, new_values)
        VALUES (
            p_table_name, p_row_key, p_operation,
            CASE WHEN g_actor_unit = l_via THEN g_actor END,
            SYS_CONTEXT('USERENV', 'SESSION_USER'),
            SYS_CONTEXT('USERENV', 'OS_USER'),
            SYS_CONTEXT('USERENV', 'HOST'),
            SYS_CONTEXT('USERENV', 'MODULE'),
            SYS_CONTEXT('USERENV', 'CLIENT_IDENTIFIER'),
            l_via,
            DBMS_TRANSACTION.LOCAL_TRANSACTION_ID,
            p_old_values, p_new_values);
    END record_change;

    FUNCTION json_pairs (p_table_name IN VARCHAR2, p_prefix IN VARCHAR2) RETURN VARCHAR2 IS
        l_sql VARCHAR2(32767);
    BEGIN
        FOR c IN (SELECT column_name FROM user_tab_columns
                   WHERE table_name = p_table_name
                     AND data_type NOT IN ('CLOB', 'BLOB', 'NCLOB', 'LONG', 'LONG RAW', 'BFILE')
                   ORDER BY column_id) LOOP
            l_sql := l_sql || CASE WHEN l_sql IS NOT NULL THEN ', ' END
                  || '''' || c.column_name || ''' VALUE ' || p_prefix || '"' || c.column_name || '"';
        END LOOP;
        RETURN 'JSON_OBJECT(' || l_sql || ' RETURNING CLOB)';
    END json_pairs;

    FUNCTION key_expr (p_key_columns IN VARCHAR2, p_prefix IN VARCHAR2) RETURN VARCHAR2 IS
        l_expr VARCHAR2(4000);
    BEGIN
        FOR k IN (SELECT TRIM(REGEXP_SUBSTR(p_key_columns, '[^,]+', 1, LEVEL)) AS col
                    FROM dual CONNECT BY REGEXP_SUBSTR(p_key_columns, '[^,]+', 1, LEVEL) IS NOT NULL) LOOP
            l_expr := l_expr || CASE WHEN l_expr IS NOT NULL THEN ' || ''|'' || ' END
                   || 'TO_CHAR(' || p_prefix || '"' || DBMS_ASSERT.SIMPLE_SQL_NAME(UPPER(k.col)) || '")';
        END LOOP;
        RETURN l_expr;
    END key_expr;

    PROCEDURE install_row_audit (
        p_table_name  IN VARCHAR2,
        p_key_columns IN VARCHAR2,
        p_baseline    IN BOOLEAN DEFAULT TRUE
    ) IS
        l_table VARCHAR2(128) := UPPER(DBMS_ASSERT.SIMPLE_SQL_NAME(p_table_name));
    BEGIN
        EXECUTE IMMEDIATE
               'CREATE OR REPLACE TRIGGER "TRG_AUD_' || l_table || '"'
            || ' AFTER INSERT OR UPDATE OR DELETE ON "' || l_table || '" FOR EACH ROW'
            || ' DECLARE l_old CLOB; l_new CLOB;'
            || ' BEGIN'
            || '   IF INSERTING OR UPDATING THEN SELECT ' || json_pairs(l_table, ':NEW.') || ' INTO l_new FROM dual; END IF;'
            || '   IF UPDATING OR DELETING THEN SELECT ' || json_pairs(l_table, ':OLD.') || ' INTO l_old FROM dual; END IF;'
            || '   audit_kit.record_change(''' || l_table || ''','
            || '     CASE WHEN DELETING THEN ' || key_expr(p_key_columns, ':OLD.')
            ||         ' ELSE ' || key_expr(p_key_columns, ':NEW.') || ' END,'
            || '     CASE WHEN INSERTING THEN ''INSERT'' WHEN UPDATING THEN ''UPDATE'' ELSE ''DELETE'' END,'
            || '     l_old, l_new);'
            || ' END;';

        IF p_baseline THEN
            EXECUTE IMMEDIATE
                   'INSERT INTO audit_row_change (table_name, row_key, operation, db_user, os_user,'
                || ' client_host, client_program, via_program, txn_id, new_values)'
                || ' SELECT :t, ' || key_expr(p_key_columns, '') || ', ''BASELINE'','
                || ' SYS_CONTEXT(''USERENV'', ''SESSION_USER''), SYS_CONTEXT(''USERENV'', ''OS_USER''),'
                || ' SYS_CONTEXT(''USERENV'', ''HOST''), SYS_CONTEXT(''USERENV'', ''MODULE''),'
                || ' ''AUDIT_KIT.INSTALL_ROW_AUDIT'', DBMS_TRANSACTION.LOCAL_TRANSACTION_ID, '
                || json_pairs(l_table, '') || ' FROM "' || l_table || '"'
                USING l_table;
            COMMIT;
        END IF;
    END install_row_audit;

    PROCEDURE protect_append_only (p_table_name IN VARCHAR2) IS
        l_table VARCHAR2(128) := UPPER(DBMS_ASSERT.SIMPLE_SQL_NAME(p_table_name));
    BEGIN
        EXECUTE IMMEDIATE
               'CREATE OR REPLACE TRIGGER "TRG_APPEND_ONLY_' || l_table || '"'
            || ' BEFORE UPDATE OR DELETE ON "' || l_table || '"'
            || ' BEGIN'
            || '   IF UPDATING OR NOT audit_purge_gate.is_open THEN'
            || '     RAISE_APPLICATION_ERROR(-20901, ''' || l_table
            ||         ' is append-only; rows leave it only through retention_kit.purge'');'
            || '   END IF;'
            || ' END;';
    END protect_append_only;
END audit_kit;
/

EXIT;
