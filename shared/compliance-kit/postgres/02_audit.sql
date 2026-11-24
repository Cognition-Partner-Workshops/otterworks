-- compliance-kit / PostgreSQL: row-change audit trail.
--   CREATE TRIGGER trg_aud_<t> AFTER INSERT OR UPDATE OR DELETE ON <t>
--     FOR EACH ROW EXECUTE FUNCTION compliance.audit_row_change_trg('<key col>'[, '<redacted col>', ...]);
-- One row per changed row in the same transaction, carrying session_user,
-- the application actor (SET LOCAL compliance.actor = '...'), client address
-- and application_name, the time, and the before/after row as JSONB. Columns
-- named after the key are stored as '[redacted]' so the trail never becomes
-- a second copy of the PII it is guarding.
CREATE SCHEMA IF NOT EXISTS compliance;

CREATE TABLE IF NOT EXISTS compliance.audit_row_change (
    change_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name     text        NOT NULL,
    row_key        text        NOT NULL,
    operation      text        NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
    app_actor      text,
    db_user        text        NOT NULL DEFAULT session_user,
    client_addr    inet                 DEFAULT inet_client_addr(),
    client_program text                 DEFAULT current_setting('application_name', true),
    txid           xid8        NOT NULL DEFAULT pg_current_xact_id(),
    old_values     jsonb,
    new_values     jsonb
);
CREATE INDEX IF NOT EXISTS ix_arc_table_key ON compliance.audit_row_change (table_name, row_key, change_id);

CREATE OR REPLACE FUNCTION compliance.audit_row_change_trg()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, compliance AS $$
DECLARE
    key_col  text := TG_ARGV[0];
    redacted text[] := TG_ARGV[1:];
    old_j    jsonb;
    new_j    jsonb;
    col      text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN old_j := to_jsonb(OLD); END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN new_j := to_jsonb(NEW); END IF;
    FOREACH col IN ARRAY coalesce(redacted, '{}') LOOP
        IF old_j ? col AND old_j ->> col IS NOT NULL THEN old_j := jsonb_set(old_j, ARRAY[col], '"[redacted]"'); END IF;
        IF new_j ? col AND new_j ->> col IS NOT NULL THEN new_j := jsonb_set(new_j, ARRAY[col], '"[redacted]"'); END IF;
    END LOOP;
    INSERT INTO compliance.audit_row_change (table_name, row_key, operation, app_actor, old_values, new_values)
    VALUES (TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
            coalesce(new_j, old_j) ->> key_col,
            TG_OP,
            nullif(current_setting('compliance.actor', true), ''),
            old_j, new_j);
    RETURN NULL;
END
$$;

-- Append-only guard for log tables: UPDATE always refused, DELETE refused
-- unless compliance.purge is running (it sets compliance.purging locally).
CREATE OR REPLACE FUNCTION compliance.append_only_trg()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' OR coalesce(current_setting('compliance.purging', true), '') <> 'on' THEN
        RAISE EXCEPTION '% is append-only; rows leave it only through compliance.purge', TG_TABLE_NAME
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN OLD;
END
$$;

DROP TRIGGER IF EXISTS trg_append_only ON compliance.audit_row_change;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON compliance.audit_row_change
    FOR EACH ROW EXECUTE FUNCTION compliance.append_only_trg();
