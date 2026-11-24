-- compliance-kit / PostgreSQL: retention purge pattern.
-- compliance.purge applies one retention rule to one table: DELETE the rows
-- the rule selects, or NULLIFY a list of columns on them (keep the record,
-- drop the personal data). dry_run => true (the default) only counts. Every
-- call, dry or not, writes one compliance.retention_run row. The predicate is
-- policy code owned by the schema owner, may use $1 (the as-of date), and is
-- never built from user input.
CREATE SCHEMA IF NOT EXISTS compliance;

CREATE TABLE IF NOT EXISTS compliance.retention_run (
    run_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_name  text        NOT NULL,
    table_name   text        NOT NULL,
    action       text        NOT NULL CHECK (action IN ('DELETE', 'NULLIFY')),
    columns      text[],
    predicate    text        NOT NULL,
    as_of        date        NOT NULL,
    dry_run      boolean     NOT NULL,
    rows_matched bigint      NOT NULL,
    rows_purged  bigint      NOT NULL,
    row_keys     text[],
    run_by       text        NOT NULL DEFAULT session_user,
    run_at       timestamptz NOT NULL DEFAULT clock_timestamp()
);

DROP TRIGGER IF EXISTS trg_append_only ON compliance.retention_run;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON compliance.retention_run
    FOR EACH ROW EXECUTE FUNCTION compliance.append_only_trg();

CREATE OR REPLACE FUNCTION compliance.purge(
    policy_name text,
    target      regclass,
    predicate   text,
    as_of       date,
    dry_run     boolean DEFAULT true,
    action      text    DEFAULT 'DELETE',
    columns     text[]  DEFAULT NULL,
    key_column  text    DEFAULT NULL
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    matched bigint;
    purged  bigint := 0;
    keys    text[];
    set_list text;
BEGIN
    IF action NOT IN ('DELETE', 'NULLIFY') THEN
        RAISE EXCEPTION 'action must be DELETE or NULLIFY, got %', action;
    END IF;
    IF action = 'NULLIFY' AND coalesce(cardinality(columns), 0) = 0 THEN
        RAISE EXCEPTION 'NULLIFY needs at least one column';
    END IF;

    EXECUTE format('SELECT count(*), %s FROM %s WHERE %s',
                   CASE WHEN key_column IS NULL THEN 'NULL::text[]'
                        ELSE format('array_agg(%I::text ORDER BY %I::text)', key_column, key_column) END,
                   target, predicate)
       INTO matched, keys USING as_of;

    IF NOT dry_run AND matched > 0 THEN
        IF action = 'DELETE' THEN
            PERFORM set_config('compliance.purging', 'on', true);
            EXECUTE format('DELETE FROM %s WHERE %s', target, predicate) USING as_of;
            GET DIAGNOSTICS purged = ROW_COUNT;
            PERFORM set_config('compliance.purging', 'off', true);
        ELSE
            SELECT string_agg(format('%I = NULL', c), ', ') INTO set_list FROM unnest(columns) AS c;
            EXECUTE format('UPDATE %s SET %s WHERE %s', target, set_list, predicate) USING as_of;
            GET DIAGNOSTICS purged = ROW_COUNT;
        END IF;
    END IF;

    INSERT INTO compliance.retention_run
        (policy_name, table_name, action, columns, predicate, as_of, dry_run, rows_matched, rows_purged, row_keys)
    VALUES (policy_name, target::text, action, columns, predicate, as_of, dry_run, matched, purged, keys);
    RETURN matched;
END
$$;

-- Only the owner (and functions it defines) may purge; it can open the audit gate.
REVOKE EXECUTE ON FUNCTION compliance.purge(text, regclass, text, date, boolean, text, text[], text) FROM PUBLIC;
