-- Run databricks-1793146609, unit pkg_dunning: OW_BILLING.PKG_DUNNING + JOB_NIGHTLY_DUNNING
-- -> ow_tp_invoicing.* (PL/pgSQL).
-- Source: services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql, schema/04_jobs.sql.
-- Package state (g_last_run_dt, g_scheduled_cnt) has no reader outside the package; the
-- scheduled count stays a local variable.

CREATE OR REPLACE FUNCTION ow_tp_invoicing.fn_overdue_accounts(p_as_of timestamp)
RETURNS TABLE (
    tenant_id     varchar,
    invoice_id    varchar,
    total         numeric,
    days_overdue  bigint,
    tenant_status varchar
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
    RETURN QUERY
        SELECT i.tenant_id, i.id, i.total,
               (p_as_of::date - i.issued_at::date)::bigint,
               CASE t.status_cd WHEN 10 THEN 'active' WHEN 20 THEN 'suspended'
                    ELSE 'UNKNOWN' END::varchar
          FROM ow_tp_invoicing.invoices i
          LEFT JOIN ow_tp_invoicing.tenants t ON t.id = i.tenant_id
         WHERE i.status_cd = 40
           AND i.issued_at::date < p_as_of::date
         ORDER BY i.issued_at, i.id;
END;
$$;

CREATE OR REPLACE PROCEDURE ow_tp_invoicing.sp_schedule_dunning(p_as_of timestamp)
LANGUAGE plpgsql
AS $$
DECLARE
    inv         record;
    v_attempt   bigint;
    v_next      timestamp;
    v_dow       varchar(3);
    v_scheduled bigint := 0;
BEGIN
    FOR inv IN (SELECT id, tenant_id FROM ow_tp_invoicing.invoices
                 WHERE status_cd = 40
                 ORDER BY issued_at, id)
    LOOP
        SELECT coalesce(max(attempt_no), 0) + 1 INTO v_attempt
          FROM ow_tp_invoicing.dunning_attempts WHERE invoice_id = inv.id;

        -- Weekend push: SAT -> Monday, SUN -> Monday (TO_CHAR 'DY' on English locale)
        v_next := p_as_of::date;
        v_dow := upper(to_char(v_next, 'DY'));
        v_next := v_next + CASE v_dow WHEN 'SAT' THEN 2 WHEN 'SUN' THEN 1 ELSE 0 END;

        BEGIN
            INSERT INTO ow_tp_invoicing.dunning_attempts (
                id, tenant_id, invoice_id, attempt_no, scheduled_for, status_cd
            ) VALUES (
                ow_tp_invoicing.f_md5_uuid(inv.id || v_attempt::text),
                inv.tenant_id, inv.id, v_attempt, v_next, 10
            );
            v_scheduled := v_scheduled + 1;
        EXCEPTION
            -- swallow absolutely everything and move on, the Oracle-legacy way
            WHEN OTHERS THEN NULL;
        END;
    END LOOP;
    CALL ow_tp_invoicing.log_msg('DUNNING', 'scheduled ' || v_scheduled::text ||
        ' attempts as of ' || to_char(p_as_of, 'DD-MON-YY'));
END;
$$;

CREATE OR REPLACE PROCEDURE ow_tp_invoicing.sp_suspend_overdue(p_as_of timestamp)
LANGUAGE plpgsql
AS $$
DECLARE
    t        record;
    v_active bigint;
BEGIN
    FOR t IN (SELECT DISTINCT i.tenant_id FROM ow_tp_invoicing.invoices i
               WHERE i.status_cd = 40
                 AND i.issued_at::date <= (p_as_of::date - 14))
    LOOP
        SELECT count(*) INTO v_active
          FROM ow_tp_invoicing.tenants WHERE id = t.tenant_id AND status_cd = 10;
        IF v_active > 0 THEN
            UPDATE ow_tp_invoicing.tenants SET status_cd = 20 WHERE id = t.tenant_id;
            UPDATE ow_tp_invoicing.subscriptions
               SET status_cd = 20, suspended_on = p_as_of::date
             WHERE tenant_id = t.tenant_id AND status_cd = 10;

            INSERT INTO ow_tp_invoicing.notifications (id, tenant_id, kind_cd, sent_at)
            SELECT ow_tp_invoicing.f_md5_uuid(t.tenant_id || 'suspension' ||
                       to_char(p_as_of::date, 'YYYY-MM-DD')),
                   t.tenant_id, 3, p_as_of::date
             WHERE NOT EXISTS (
                   SELECT 1 FROM ow_tp_invoicing.notifications
                    WHERE tenant_id = t.tenant_id AND kind_cd = 3
                      AND sent_at = p_as_of::date::timestamp);

            CALL ow_tp_invoicing.log_msg('DUNNING', 'suspended tenant=' || t.tenant_id);
        END IF;
    END LOOP;
END;
$$;

-- DBMS_SCHEDULER JOB_NIGHTLY_DUNNING (disabled at source): FREQ=DAILY BYHOUR=2,
-- TRUNC(SYSDATE) -> current_date.
CREATE OR REPLACE PROCEDURE ow_tp_invoicing.job_nightly_dunning()
LANGUAGE plpgsql
AS $$
BEGIN
    CALL ow_tp_invoicing.sp_schedule_dunning(current_date::timestamp);
    CALL ow_tp_invoicing.sp_suspend_overdue(current_date::timestamp);
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
$$;
