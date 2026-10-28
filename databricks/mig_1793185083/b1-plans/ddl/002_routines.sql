-- u-plans routines, Lakebase database ow_tp branch mig-1793185083, schema
-- mig_1793185083. plpgsql port of OW_BILLING.PKG_PLANS (fn_list_plans,
-- fn_entitlement, sp_change_plan) plus the subscriptions triggers
-- trg_subscriptions_hist and trg_sub_no_uncancel.
--
-- Conversion notes:
--  * pkg_ow_util.log_msg audit writes are dropped: billing_audit_log is not in
--    this unit's mapping spec and the call is a no-op against missing tables in
--    the source (it swallows errors).
--  * pkg_plans globals g_last_tenant_id / g_last_plan_code have no package state
--    in Postgres; they were a read cache only, so they are folded into
--    fn_entitlement's body as a discarded SELECT that preserves the source's
--    exception-swallowing behavior.
--  * pkg_ow_util.f_md5_uuid is inlined in sp_change_plan (md5 hex -> 8-4-4-4-12).

-- Idempotent against partial deploys from the suspended first attempt: the
-- OUT-parameter shape may differ, so drop before creating.
DROP FUNCTION IF EXISTS mig_1793185083.fn_list_plans();
DROP FUNCTION IF EXISTS mig_1793185083.fn_entitlement(varchar, date);
DROP FUNCTION IF EXISTS mig_1793185083.sp_change_plan(varchar, varchar, date);
DROP FUNCTION IF EXISTS mig_1793185083.fn_entitlement(character varying, date);
DROP FUNCTION IF EXISTS mig_1793185083.sp_change_plan(character varying, character varying, date);

CREATE OR REPLACE FUNCTION mig_1793185083.fn_list_plans()
RETURNS TABLE (
    plan_id        varchar(36),
    code           varchar(50),
    tier           text,
    monthly_fee    numeric(12, 2),
    included_units bigint,
    overage_rate   numeric(12, 6)
)
LANGUAGE sql STABLE AS $$
    SELECT id, code,
           CASE tier_cd WHEN 1 THEN 'starter' WHEN 2 THEN 'growth'
                        WHEN 3 THEN 'scale' ELSE 'UNKNOWN' END,
           monthly_fee, included_units, overage_rate
      FROM mig_1793185083.plans
     WHERE COALESCE(active_yn, 'N') = 'Y'
     ORDER BY monthly_fee, code
$$;

CREATE OR REPLACE FUNCTION mig_1793185083.fn_entitlement(
    p_tenant_id varchar, p_on date)
RETURNS TABLE (
    tenant_id           varchar(36),
    plan_code           varchar(50),
    tier                text,
    monthly_fee         numeric(12, 2),
    included_units      bigint,
    subscription_status text,
    effective_on        date
)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_last_plan_code varchar(50);
BEGIN
    -- g_last_plan_code := <latest covering sub's plan code>, errors swallowed,
    -- same as the source's SELECT INTO under WHEN OTHERS THEN NULL.
    BEGIN
        SELECT p.code INTO v_last_plan_code
          FROM mig_1793185083.subscriptions s
          LEFT JOIN mig_1793185083.plans p ON p.id = s.plan_id
         WHERE s.tenant_id = p_tenant_id
           AND s.starts_on <= p_on
           AND COALESCE(s.ends_on, DATE '1999-12-31') >= p_on
         LIMIT 1;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    RETURN QUERY
    SELECT t.id, p.code,
           CASE p.tier_cd WHEN 1 THEN 'starter' WHEN 2 THEN 'growth'
                          WHEN 3 THEN 'scale' ELSE 'UNKNOWN' END,
           p.monthly_fee, p.included_units,
           CASE s.status_cd WHEN 10 THEN 'active' WHEN 20 THEN 'suspended'
                            WHEN 30 THEN 'cancelled' ELSE 'UNKNOWN' END,
           GREATEST(s.starts_on, p_on)
      FROM mig_1793185083.tenants t
      JOIN mig_1793185083.subscriptions s ON s.tenant_id = t.id
      LEFT JOIN mig_1793185083.plans p ON p.id = s.plan_id
     WHERE t.id = p_tenant_id
       AND s.starts_on <= p_on
       AND (s.ends_on IS NULL OR s.ends_on >= p_on)
     ORDER BY s.starts_on DESC
     LIMIT 1;
END;
$$;

CREATE OR REPLACE FUNCTION mig_1793185083.sp_change_plan(
    p_tenant_id varchar, p_plan_id varchar, p_effective_on date)
RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    r       record;
    v_new_id varchar(36);
    v_md5    text;
BEGIN
    FOR r IN
        SELECT id, status_cd
          FROM mig_1793185083.subscriptions
         WHERE tenant_id = p_tenant_id
           AND ends_on IS NULL
           AND starts_on < p_effective_on
         FOR UPDATE
    LOOP
        UPDATE mig_1793185083.subscriptions
           SET ends_on = p_effective_on - 1,
               status_cd = CASE WHEN r.status_cd = 30 THEN 30 ELSE 10 END
         WHERE id = r.id;
    END LOOP;

    v_md5 := md5(p_tenant_id || p_plan_id || to_char(p_effective_on, 'YYYY-MM-DD'));
    v_new_id := substr(v_md5, 1, 8) || '-' || substr(v_md5, 9, 4) || '-' ||
                substr(v_md5, 13, 4) || '-' || substr(v_md5, 17, 4) || '-' ||
                substr(v_md5, 21, 12);

    INSERT INTO mig_1793185083.subscriptions (id, tenant_id, plan_id, starts_on, status_cd)
    VALUES (v_new_id, p_tenant_id, p_plan_id, p_effective_on, 10);
END;
$$;

-- trg_subscriptions_hist: AFTER UPDATE OR DELETE on subscriptions; archives the
-- OLD image with seq_subscriptions_hist and the DD-MON-YY HH24:MI:SS stamp.
CREATE OR REPLACE FUNCTION mig_1793185083.trg_subscriptions_hist_fn()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO mig_1793185083.subscriptions_hist (
        hist_id, hist_dt, hist_dt_raw, hist_op, id, tenant_id, plan_id,
        starts_on, ends_on, status_cd, suspended_on)
    VALUES (
        nextval('mig_1793185083.seq_subscriptions_hist'),
        to_char(now(), 'DD-MON-YY HH24:MI:SS'),
        to_char(now(), 'DD-MON-YY HH24:MI:SS'),
        CASE WHEN TG_OP = 'DELETE' THEN 'DEL' ELSE 'UPD' END,
        OLD.id, OLD.tenant_id, OLD.plan_id,
        OLD.starts_on, OLD.ends_on, OLD.status_cd, OLD.suspended_on);
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_subscriptions_hist ON mig_1793185083.subscriptions;
CREATE TRIGGER trg_subscriptions_hist
    AFTER UPDATE OR DELETE ON mig_1793185083.subscriptions
    FOR EACH ROW EXECUTE FUNCTION mig_1793185083.trg_subscriptions_hist_fn();

-- trg_sub_no_uncancel: BEFORE UPDATE OF status_cd; a cancelled subscription
-- (status_cd 30) stays cancelled.
CREATE OR REPLACE FUNCTION mig_1793185083.trg_sub_no_uncancel_fn()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status_cd = 30 THEN
        NEW.status_cd := 30;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sub_no_uncancel ON mig_1793185083.subscriptions;
CREATE TRIGGER trg_sub_no_uncancel
    BEFORE UPDATE OF status_cd ON mig_1793185083.subscriptions
    FOR EACH ROW EXECUTE FUNCTION mig_1793185083.trg_sub_no_uncancel_fn();
