-- Run databricks-1793146609, unit pkg_ow_util: OW_BILLING.PKG_OW_UTIL + JOB_PURGE_AUDIT_LOG
-- -> ow_tp_invoicing.* (PL/pgSQL).
-- Source: services/legacy-billing/db/oracle/packages/01_pkg_util.sql, schema/04_jobs.sql.
-- Package state (g_call_count, g_last_module, g_last_uuid) has no reader outside the package and is dropped.
-- log_msg is not autonomous; its row commits or rolls back with the caller.

CREATE OR REPLACE FUNCTION ow_tp_invoicing.f_md5_uuid(p_input varchar)
RETURNS varchar
LANGUAGE sql IMMUTABLE STRICT
AS $$
    SELECT substr(h, 1, 8) || '-' || substr(h, 9, 4) || '-' || substr(h, 13, 4) || '-' ||
           substr(h, 17, 4) || '-' || substr(h, 21, 12)
      FROM (SELECT lower(md5(p_input)) AS h) x
$$;

CREATE OR REPLACE FUNCTION ow_tp_invoicing.f_code_desc(p_type varchar, p_val numeric)
RETURNS varchar
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v_desc varchar(80);
BEGIN
    SELECT code_desc INTO STRICT v_desc
      FROM ow_tp_invoicing.codes
     WHERE code_type = p_type AND code_val = p_val;
    RETURN v_desc;
EXCEPTION
    WHEN no_data_found THEN
        RETURN 'UNKNOWN(' || regexp_replace(regexp_replace(regexp_replace((coalesce(p_val, -1))::text, '(\.\d*?)0+$', '\1'), '\.$', ''), '^(-?)0\.', '\1.') || ')';
END;
$$;

CREATE OR REPLACE FUNCTION ow_tp_invoicing.f_dt2str(p_dt timestamp)
RETURNS varchar
LANGUAGE sql IMMUTABLE
AS $$
    SELECT to_char(p_dt, 'DD-MON-YY')
$$;

-- TO_DATE(p_str, 'DD-MON-YY'): Oracle YY resolves into the current century; any parse error is NULL.
CREATE OR REPLACE FUNCTION ow_tp_invoicing.f_str2dt(p_str varchar)
RETURNS timestamp
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v_parts text[];
    v_year  int;
BEGIN
    IF p_str IS NULL THEN
        RETURN NULL;
    END IF;
    v_parts := regexp_match(btrim(p_str), '^(\d{1,2})-([A-Za-z]{3})-(\d{1,2})$');
    IF v_parts IS NULL THEN
        RETURN NULL;
    END IF;
    v_year := (extract(year FROM current_date)::int / 100) * 100 + v_parts[3]::int;
    RETURN to_timestamp(v_parts[1] || '-' || upper(v_parts[2]) || '-' || v_year::text, 'DD-MON-YYYY')
           AT TIME ZONE 'UTC';
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$;

CREATE OR REPLACE PROCEDURE ow_tp_invoicing.log_msg(p_module varchar, p_message varchar)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO ow_tp_invoicing.billing_audit_log (module, message)
    VALUES (substr(p_module, 1, 30), substr(p_message, 1, 4000));
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
$$;

-- DBMS_SCHEDULER JOB_PURGE_AUDIT_LOG (disabled at source): 90-day retention, errors swallowed.
CREATE OR REPLACE PROCEDURE ow_tp_invoicing.job_purge_audit_log()
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM ow_tp_invoicing.billing_audit_log
     WHERE logged_at < localtimestamp - interval '90 days';
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
$$;
