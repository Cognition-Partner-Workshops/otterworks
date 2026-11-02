-- OW_BILLING.PKG_OW_UTIL as PL/pgSQL on the Lakebase branch. The package namespace becomes a
-- schema so callers keep writing pkg_ow_util.log_msg(...). Converted by hand from
-- services/legacy-billing/db/oracle/packages/01_pkg_util.sql against the oracle dialect traps:
--   trap 11  package globals g_call_count / g_last_module / g_last_uuid: nothing outside the
--            package reads them; dropped (no session state on the target).
--   trap 13  f_str2dt swallows parse errors into NULL on Oracle; kept (callers rely on NULL),
--            log_msg's swallowed error becomes a WARNING instead of silence.
--   trap 14  log_msg is an AUTONOMOUS_TRANSACTION on Oracle; Postgres has none, so the audit row
--            joins the caller's transaction (lost on rollback). Recorded as a data finding;
--            BILLING_AUDIT_LOG is graded by_design_unverified in grading.json.
--   trap 20  TO_DATE(..., 'DD-MON-YY'): Oracle YY takes the current century, Postgres YY the
--            year nearest 2020; identical for 1970-2069 inputs, documented for the rest.
CREATE SCHEMA IF NOT EXISTS pkg_ow_util;

-- STANDARD_HASH(UTL_RAW.CAST_TO_RAW(p), 'MD5') over the UTF-8 bytes, formatted 8-4-4-4-12.
CREATE OR REPLACE FUNCTION pkg_ow_util.f_md5_uuid(p_input text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT substr(h, 1, 8) || '-' || substr(h, 9, 4) || '-' || substr(h, 13, 4) || '-' ||
           substr(h, 17, 4) || '-' || substr(h, 21, 12)
    FROM (SELECT md5(p_input) AS h) s
$$;

-- The 2009 EXECUTE IMMEDIATE lookup becomes a static query; the magic numbers stay in CODES.
-- Oracle TO_CHAR(NVL(p_val, -1)) prints the shortest decimal form, hence the FM format + trims.
CREATE OR REPLACE FUNCTION pkg_ow_util.f_code_desc(p_type text, p_val numeric) RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_desc text;
BEGIN
    SELECT code_desc INTO v_desc
      FROM mig_unt19_20261030_slice_0.codes
     WHERE code_type = p_type AND code_val = p_val;
    IF NOT FOUND THEN
        RETURN 'UNKNOWN(' || rtrim(rtrim(to_char(coalesce(p_val, -1),
                             'FM999999999999999999990.9999999999'), '0'), '.') || ')';
    END IF;
    RETURN v_desc;
END
$$;

CREATE OR REPLACE FUNCTION pkg_ow_util.f_dt2str(p_dt timestamp) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT to_char(p_dt, 'DD-MON-YY')
$$;

CREATE OR REPLACE FUNCTION pkg_ow_util.f_str2dt(p_str text) RETURNS timestamp
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    RETURN to_date(p_str, 'DD-MON-YY')::timestamp;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;   -- dirty dates come back as NULL, as on Oracle
END
$$;

-- Logger. Not autonomous (trap 14); a failure is reported as a WARNING and never raised to the
-- caller, matching the Oracle contract that logging can never fail business code.
CREATE OR REPLACE PROCEDURE pkg_ow_util.log_msg(p_module text, p_message text)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO mig_unt19_20261030_slice_0.billing_audit_log (module, message)
    VALUES (substr(p_module, 1, 30), substr(p_message, 1, 4000));
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'pkg_ow_util.log_msg swallowed %: %', SQLSTATE, SQLERRM;
END
$$;
