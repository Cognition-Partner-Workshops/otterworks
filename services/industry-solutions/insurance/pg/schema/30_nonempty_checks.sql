-- Oracle stores '' as NULL, so a NOT NULL VARCHAR2 column rejects an empty
-- string (ORA-01400). PostgreSQL keeps '' as a value; every NOT NULL string
-- column in both schemas gets CHECK (col <> '') to keep Oracle's rejection
-- (decision D3 B). Nullable columns are left alone.
\set ON_ERROR_STOP on
DO $$
DECLARE
    c record;
BEGIN
    FOR c IN SELECT table_schema, table_name, column_name
               FROM information_schema.columns
              WHERE table_schema IN ('commission_pay', 'commission_dw')
                AND data_type = 'character varying'
                AND is_nullable = 'NO'
              ORDER BY table_schema, table_name, ordinal_position LOOP
        EXECUTE format('ALTER TABLE %I.%I ADD CONSTRAINT %I CHECK (%I <> %L)',
                       c.table_schema, c.table_name,
                       'ck_' || c.table_name || '_' || c.column_name || '_nonempty',
                       c.column_name, '');
    END LOOP;
END;
$$;
