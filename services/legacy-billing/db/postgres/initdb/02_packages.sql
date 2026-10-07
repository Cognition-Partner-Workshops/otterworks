-- OW_BILLING PL/SQL packages on PostgreSQL 15. Each Oracle package becomes a
-- schema of the same name (pkg_plans.fn_list_plans keeps its call name).
--   SYS_REFCURSOR functions -> set-returning functions (SELECT * FROM ...)
--   procedures              -> PROCEDURE (CALL ...)
--   package globals         -> composite return values; nothing reads them
--                              from outside the package, so no state is kept
--   DUP_VAL_ON_INDEX        -> unique_violation
-- Oracle propagates NULL through GREATEST/LEAST; Postgres ignores NULL
-- arguments. Every call site where an operand can be NULL is guarded so the
-- Oracle result is preserved.
\set ON_ERROR_STOP on
SET ROLE ow_billing;
SET search_path = ow_billing, public;

-- ---------------------------------------------------------------------------
-- pkg_ow_util
-- ---------------------------------------------------------------------------

-- Oracle treats '' as NULL, so f_md5_uuid(NULL) = md5 of the empty string.
CREATE FUNCTION pkg_ow_util.f_md5_uuid(p_input text) RETURNS varchar
LANGUAGE sql IMMUTABLE AS $$
    SELECT substr(h, 1, 8) || '-' || substr(h, 9, 4) || '-' ||
           substr(h, 13, 4) || '-' || substr(h, 17, 4) || '-' || substr(h, 21, 12)
      FROM (SELECT md5(coalesce(p_input, '')) AS h) x
$$;

-- TO_CHAR(number) with no format: no trailing zeros, no leading zero ('.5').
CREATE FUNCTION pkg_ow_util.f_num2char(p_val numeric) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
             WHEN p_val IS NULL THEN NULL
             WHEN t LIKE '0.%' THEN substr(t, 2)
             WHEN t LIKE '-0.%' THEN '-' || substr(t, 3)
             ELSE t
           END
      FROM (SELECT trim_scale(p_val)::text AS t) x
$$;

CREATE FUNCTION pkg_ow_util.f_code_desc(p_type varchar, p_val numeric) RETURNS varchar
LANGUAGE plpgsql STABLE SET search_path = ow_billing, public AS $$
DECLARE
    v_desc varchar(80);
BEGIN
    SELECT code_desc INTO v_desc FROM codes WHERE code_type = p_type AND code_val = p_val;
    IF NOT FOUND THEN
        RETURN 'UNKNOWN(' || pkg_ow_util.f_num2char(coalesce(p_val, -1)) || ')';
    END IF;
    RETURN v_desc;
END
$$;

-- Oracle ADD_MONTHS: a last-day-of-month input maps to the last day of the
-- target month (Postgres interval arithmetic would keep the day number).
CREATE FUNCTION pkg_ow_util.add_months(p_dt date, p_months integer) RETURNS date
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
             WHEN p_dt = (date_trunc('month', p_dt) + interval '1 month - 1 day')::date
             THEN (date_trunc('month', p_dt) + make_interval(months => p_months + 1)
                   - interval '1 day')::date
             ELSE (p_dt + make_interval(months => p_months))::date
           END
$$;

CREATE FUNCTION pkg_ow_util.f_dt2str(p_dt date) RETURNS varchar
LANGUAGE sql IMMUTABLE AS $$
    SELECT to_char(p_dt, 'DD-MON-YY')
$$;

-- Oracle 'YY' puts the year in the current century; Postgres 'YY' picks the
-- year nearest 2020. Rebuild the year as 20YY to keep Oracle's answer.
-- Unparseable input returns NULL, as before.
CREATE FUNCTION pkg_ow_util.f_str2dt(p_str varchar) RETURNS date
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_dt date;
BEGIN
    IF p_str IS NULL OR p_str !~* '^\s*[0-9]{1,2}-[A-Z]{3}-[0-9]{2}\s*$' THEN
        RETURN NULL;
    END IF;
    v_dt := to_date(p_str, 'DD-MON-YY');
    RETURN make_date((extract(century FROM current_date)::int - 1) * 100
                         + extract(year FROM v_dt)::int % 100,
                     extract(month FROM v_dt)::int, extract(day FROM v_dt)::int);
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END
$$;

-- Oracle logged through an AUTONOMOUS_TRANSACTION, so the row survives a
-- rollback of the caller. Postgres has no autonomous transactions; the row
-- is written on a separate dblink session (as ow_billing_audit, via the
-- ow_billing_audit_loopback user mapping) that autocommits. The session is
-- kept per backend and reopened if it died. Logging failures are still
-- swallowed, as on Oracle.
CREATE PROCEDURE pkg_ow_util.log_msg(p_module varchar, p_message text)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    c_conn CONSTANT text := 'ow_billing_audit';
    v_sql  text := format(
        'INSERT INTO ow_billing.billing_audit_log (module, message) VALUES (%L, %L)',
        substr(p_module, 1, 30), substr(p_message, 1, 4000));
BEGIN
    FOR attempt IN 1..2 LOOP
        BEGIN
            IF NOT coalesce(c_conn = ANY (ow_billing_dblink.dblink_get_connections()), false) THEN
                PERFORM ow_billing_dblink.dblink_connect(c_conn, 'ow_billing_audit_loopback');
            END IF;
            PERFORM ow_billing_dblink.dblink_exec(c_conn, v_sql);
            RETURN;
        EXCEPTION
            WHEN OTHERS THEN
                BEGIN
                    PERFORM ow_billing_dblink.dblink_disconnect(c_conn);
                EXCEPTION
                    WHEN OTHERS THEN NULL;
                END;
        END;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------------
-- pkg_plans
-- ---------------------------------------------------------------------------

CREATE FUNCTION pkg_plans.fn_list_plans()
RETURNS TABLE (plan_id varchar, code varchar, tier text, monthly_fee numeric,
               included_units bigint, overage_rate numeric)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
#variable_conflict use_column
BEGIN
    CALL pkg_ow_util.log_msg('PLANS', 'fn_list_plans');
    RETURN QUERY
        SELECT p.id, p.code,
               CASE p.tier_cd WHEN 1 THEN 'starter' WHEN 2 THEN 'growth'
                              WHEN 3 THEN 'scale' ELSE 'UNKNOWN' END,
               p.monthly_fee, p.included_units, p.overage_rate
          FROM plans p
         WHERE coalesce(p.active_yn, 'N') = 'Y'
         ORDER BY p.monthly_fee, p.code;
END
$$;

CREATE FUNCTION pkg_plans.fn_entitlement(p_tenant_id varchar, p_on date)
RETURNS TABLE (tenant_id varchar, plan_code varchar, tier text, monthly_fee numeric,
               included_units bigint, subscription_status text, effective_on date)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
#variable_conflict use_column
BEGIN
    RETURN QUERY
        SELECT t.id, p.code,
               CASE p.tier_cd WHEN 1 THEN 'starter' WHEN 2 THEN 'growth'
                              WHEN 3 THEN 'scale' ELSE 'UNKNOWN' END,
               p.monthly_fee, p.included_units,
               CASE s.status_cd WHEN 10 THEN 'active' WHEN 20 THEN 'suspended'
                                WHEN 30 THEN 'cancelled' ELSE 'UNKNOWN' END,
               GREATEST(s.starts_on, p_on)
          FROM tenants t
          JOIN subscriptions s ON s.tenant_id = t.id
          LEFT JOIN plans p ON p.id = s.plan_id
         WHERE t.id = p_tenant_id
           AND s.starts_on <= p_on
           AND (s.ends_on IS NULL OR s.ends_on >= p_on)
         ORDER BY s.starts_on DESC
         LIMIT 1;
END
$$;

CREATE PROCEDURE pkg_plans.sp_change_plan(p_tenant_id varchar, p_plan_id varchar,
                                          p_effective_on date)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    r record;
BEGIN
    CALL pkg_ow_util.log_msg('PLANS', concat('sp_change_plan tenant=', p_tenant_id,
        ' plan=', p_plan_id, ' eff=', to_char(p_effective_on, 'YYYY-MM-DD')));
    -- "Cancelled stays cancelled" is also enforced by trg_sub_no_uncancel.
    FOR r IN SELECT id, status_cd
               FROM subscriptions
              WHERE tenant_id = p_tenant_id
                AND ends_on IS NULL
                AND starts_on < p_effective_on
                FOR UPDATE
    LOOP
        UPDATE subscriptions
           SET ends_on = p_effective_on - 1,
               status_cd = CASE WHEN r.status_cd = 30 THEN 30 ELSE 10 END
         WHERE id = r.id;
    END LOOP;
    INSERT INTO subscriptions (id, tenant_id, plan_id, starts_on, status_cd)
    VALUES (pkg_ow_util.f_md5_uuid(concat(p_tenant_id, p_plan_id,
                                          to_char(p_effective_on, 'YYYY-MM-DD'))),
            p_tenant_id, p_plan_id, p_effective_on, 10);
END
$$;

-- ---------------------------------------------------------------------------
-- pkg_rating
-- ---------------------------------------------------------------------------

-- What Oracle kept in pkg_rating's package globals between calls.
CREATE TYPE pkg_rating.rating_state AS (
    tenant_id          varchar(36),
    period_start       date,
    period_end         date,
    used_units         numeric,
    quota_units        numeric,
    rollover_units     numeric,
    billable_units     numeric,
    first_tier_units   numeric,
    second_tier_units  numeric,
    overage_amount     numeric
);

CREATE FUNCTION pkg_rating.compute_rating(p_tenant_id varchar, p_period_start date,
                                          p_period_end date)
RETURNS pkg_rating.rating_state
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    g            pkg_rating.rating_state;
    v_sub_status smallint;
    v_suspended  date;
    v_plan_id    varchar(36);
    v_included   numeric;
    v_rate       numeric;
    v_prior      numeric;
    v_factor     numeric;
BEGIN
    g.tenant_id := p_tenant_id;
    g.period_start := p_period_start;
    g.period_end := p_period_end;

    SELECT s.status_cd, s.suspended_on, s.plan_id
      INTO v_sub_status, v_suspended, v_plan_id
      FROM subscriptions s
     WHERE s.tenant_id = p_tenant_id
       AND s.starts_on <= p_period_end
       AND (s.ends_on IS NULL OR s.ends_on >= p_period_start)
     ORDER BY s.starts_on DESC
     LIMIT 1;

    SELECT included_units, overage_rate INTO v_included, v_rate
      FROM plans WHERE id = v_plan_id;

    -- Oracle compared TO_CHAR(.., 'YYYYMMDD') strings: a calendar-day range.
    SELECT coalesce(sum(coalesce(u.units, 0)), 0) INTO g.used_units
      FROM usage_events u
     WHERE u.tenant_id = p_tenant_id
       AND u.occurred_at::date BETWEEN p_period_start AND p_period_end;

    SELECT coalesce(sum(coalesce(rr.rollover_units, 0)), 0) INTO v_prior
      FROM rating_results rr
      JOIN rating_periods rp ON rp.id = rr.period_id
     WHERE rp.tenant_id = p_tenant_id
       AND rp.period_start < p_period_start
       AND rp.period_start >= pkg_ow_util.add_months(p_period_start, -3);

    -- Both operands are non-NULL here, so LEAST/GREATEST agree with Oracle.
    v_prior := LEAST(coalesce(2 * v_included, v_prior), v_prior);
    g.quota_units := v_included;
    g.rollover_units := LEAST(v_prior, coalesce(v_included * 2, v_prior));
    g.billable_units := GREATEST(coalesce(g.used_units - g.rollover_units - v_included, 0), 0);
    -- Tier break at 101 units, as in Oracle.
    g.first_tier_units := LEAST(g.billable_units, 101);
    g.second_tier_units := GREATEST(g.billable_units - 101, 0);
    g.overage_amount := round(g.first_tier_units * v_rate
                              + g.second_tier_units * v_rate * 1.5, 2);

    IF v_sub_status = 20 AND v_suspended IS NOT NULL
       AND v_suspended BETWEEN p_period_start AND p_period_end THEN
        -- 38 decimal places, close to Oracle NUMBER's 38 significant digits.
        v_factor := (p_period_end - v_suspended + 1)::numeric(60, 38)
                    / (p_period_end - p_period_start + 1);
        g.billable_units := round(g.billable_units * v_factor);
        g.overage_amount := round(g.overage_amount * v_factor, 2);
    END IF;

    CALL pkg_ow_util.log_msg('RATING', concat('compute tenant=', p_tenant_id,
        ' used=', pkg_ow_util.f_num2char(coalesce(g.used_units, -1)),
        ' billable=', pkg_ow_util.f_num2char(coalesce(g.billable_units, -1))));
    RETURN g;
END
$$;

CREATE FUNCTION pkg_rating.fn_usage_rating(p_tenant_id varchar, p_period_start date,
                                           p_period_end date)
RETURNS SETOF pkg_rating.rating_state
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    RETURN NEXT pkg_rating.compute_rating(p_tenant_id, p_period_start, p_period_end);
END
$$;

CREATE FUNCTION pkg_rating.fn_usage_summary(p_tenant_id varchar, p_period_start date,
                                            p_period_end date)
RETURNS TABLE (kind text, event_count bigint, units numeric)
LANGUAGE sql STABLE SET search_path = ow_billing, public AS $$
    SELECT CASE u.kind_cd WHEN 1 THEN 'api' WHEN 2 THEN 'storage'
                          WHEN 3 THEN 'compute' ELSE 'UNKNOWN' END,
           count(*),
           coalesce(sum(u.units), 0)::numeric
      FROM usage_events u
     WHERE u.tenant_id = p_tenant_id
       AND u.occurred_at::date BETWEEN p_period_start AND p_period_end
     GROUP BY 1
     ORDER BY 1
$$;

CREATE PROCEDURE pkg_rating.sp_finalize_rating(p_tenant_id varchar, p_period_start date,
                                               p_period_end date)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    v_period_id varchar(36);
    v_result_id varchar(36);
    v_sub_id    varchar(36);
    g           pkg_rating.rating_state;
    v_rollover  numeric;
BEGIN
    v_period_id := pkg_ow_util.f_md5_uuid(concat(p_tenant_id,
                                                 to_char(p_period_start, 'YYYY-MM-DD')));
    SELECT s.id INTO v_sub_id
      FROM subscriptions s
     WHERE s.tenant_id = p_tenant_id
       AND s.starts_on <= p_period_end
       AND (s.ends_on IS NULL OR s.ends_on >= p_period_start)
     ORDER BY s.starts_on DESC
     LIMIT 1;

    BEGIN
        INSERT INTO rating_periods (id, tenant_id, period_start, period_end)
        VALUES (v_period_id, p_tenant_id, p_period_start, p_period_end);
    EXCEPTION
        WHEN unique_violation THEN
            UPDATE rating_periods
               SET period_end = p_period_end
             WHERE tenant_id = p_tenant_id
               AND period_start = p_period_start;
    END;

    g := pkg_rating.compute_rating(p_tenant_id, p_period_start, p_period_end);
    v_result_id := pkg_ow_util.f_md5_uuid(v_period_id);
    -- Oracle GREATEST(NULL - x, 0) is NULL; keep it NULL.
    v_rollover := CASE WHEN g.quota_units IS NULL OR g.used_units IS NULL THEN NULL
                       ELSE GREATEST(g.quota_units - g.used_units, 0) END;
    BEGIN
        INSERT INTO rating_results (
            id, period_id, subscription_id, used_units, quota_units,
            rollover_units, billable_units, overage_amount, created_at
        ) VALUES (
            v_result_id, v_period_id, v_sub_id, g.used_units, g.quota_units,
            v_rollover, g.billable_units, g.overage_amount, p_period_end::timestamp
        );
    EXCEPTION
        WHEN unique_violation THEN
            UPDATE rating_results
               SET used_units = g.used_units,
                   rollover_units = v_rollover,
                   billable_units = g.billable_units,
                   overage_amount = g.overage_amount
             WHERE id = v_result_id;
    END;
    CALL pkg_ow_util.log_msg('RATING', concat('finalized period=', v_period_id));
END
$$;

-- ---------------------------------------------------------------------------
-- pkg_invoicing
-- ---------------------------------------------------------------------------

-- What Oracle kept in pkg_invoicing's package globals.
CREATE TYPE pkg_invoicing.preview_state AS (
    plan_code  varchar(50),
    plan_fee   numeric,
    overage    numeric,
    tax        numeric,
    credit     numeric
);

CREATE FUNCTION pkg_invoicing.compute_preview(p_tenant_id varchar, p_period_start date,
                                              p_period_end date)
RETURNS pkg_invoicing.preview_state
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    TAX_RATE CONSTANT numeric := 0.0825;   -- hardcoded 2011 combined rate
    g        pkg_invoicing.preview_state;
    v_exempt char(1);
BEGIN
    SELECT p.code, p.monthly_fee INTO g.plan_code, g.plan_fee
      FROM subscriptions s
      JOIN plans p ON p.id = s.plan_id
     WHERE s.tenant_id = p_tenant_id
       AND s.starts_on <= p_period_end
       AND (s.ends_on IS NULL OR s.ends_on >= p_period_start)
     ORDER BY s.starts_on DESC
     LIMIT 1;

    g.overage := (pkg_rating.compute_rating(p_tenant_id, p_period_start, p_period_end)).overage_amount;

    SELECT coalesce(sum(coalesce(remaining_amount, 0)), 0) INTO g.credit
      FROM credit_notes
     WHERE tenant_id = p_tenant_id AND remaining_amount > 0;

    SELECT coalesce(tax_exempt_yn, 'N') INTO v_exempt FROM tenants WHERE id = p_tenant_id;
    IF NOT FOUND THEN
        v_exempt := 'N';
    END IF;
    -- NULL plan fee / overage propagates to NULL tax, as in Oracle.
    g.tax := CASE WHEN v_exempt = 'Y' THEN 0 ELSE (g.plan_fee + g.overage) * TAX_RATE END;
    RETURN g;
END
$$;

CREATE FUNCTION pkg_invoicing.fn_invoice_preview(p_tenant_id varchar, p_period_start date,
                                                 p_period_end date)
RETURNS TABLE (line_no integer, line_type text, description varchar, amount numeric,
               tax_amount numeric, credit_applied numeric, total numeric)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    g            pkg_invoicing.preview_state;
    v_charge_cap numeric;
    v_credit_app numeric;
BEGIN
    g := pkg_invoicing.compute_preview(p_tenant_id, p_period_start, p_period_end);
    v_charge_cap := round(g.plan_fee + g.overage + g.tax, 2);
    v_credit_app := LEAST(g.credit, coalesce(v_charge_cap, g.credit));
    RETURN QUERY VALUES
        (1, 'plan',   g.plan_code,      round(g.plan_fee, 2), 0::numeric, 0::numeric, round(g.plan_fee, 2)),
        (2, 'usage',  'usage overage',  round(g.overage, 2),  0, 0, round(g.overage, 2)),
        (3, 'tax',    'regional tax',   g.tax / 2,            0, 0, g.tax / 2),
        (4, 'tax',    'local tax',      g.tax / 2,            0, 0, g.tax / 2),
        (5, 'credit', 'credit notes',   0,                    0, v_credit_app, -v_credit_app);
END
$$;

CREATE FUNCTION pkg_invoicing.fn_invoice_lines(p_invoice_id varchar)
RETURNS TABLE (line_no integer, line_type varchar, description varchar, amount numeric)
LANGUAGE sql STABLE SET search_path = ow_billing, public AS $$
    SELECT line_no, line_type, description, amount
      FROM invoice_lines
     WHERE invoice_id = p_invoice_id
     ORDER BY line_no
$$;

CREATE PROCEDURE pkg_invoicing.sp_issue_invoice(p_tenant_id varchar, p_period_start date,
                                                p_period_end date)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    v_period_id  varchar(36);
    v_invoice_id varchar(36);
    l            record;
    r            record;
    v_subtotal   numeric := 0;
    v_tax        numeric := 0;
    v_total      numeric := 0;
    v_credit     numeric := 0;
BEGIN
    v_period_id := pkg_ow_util.f_md5_uuid(concat(p_tenant_id,
                                                 to_char(p_period_start, 'YYYY-MM-DD')));
    v_invoice_id := pkg_ow_util.f_md5_uuid(concat(v_period_id, 'invoice'));
    CALL pkg_rating.sp_finalize_rating(p_tenant_id, p_period_start, p_period_end);

    BEGIN
        INSERT INTO invoices (id, tenant_id, period_id, issued_at, subtotal, tax, total, status_cd)
        VALUES (v_invoice_id, p_tenant_id, v_period_id, p_period_end::timestamp, 0, 0, 0, 20);
    EXCEPTION
        WHEN unique_violation THEN
            UPDATE invoices SET status_cd = 20 WHERE id = v_invoice_id;
    END;

    -- Rebuild the lines from scratch on every issue.
    DELETE FROM invoice_lines WHERE invoice_id = v_invoice_id;
    FOR l IN SELECT * FROM pkg_invoicing.fn_invoice_preview(p_tenant_id, p_period_start, p_period_end)
    LOOP
        INSERT INTO invoice_lines (id, invoice_id, line_no, line_type, description, amount)
        VALUES (pkg_ow_util.f_md5_uuid(concat(v_invoice_id, l.line_no::text)),
                v_invoice_id, l.line_no, l.line_type, l.description,
                CASE WHEN l.line_type = 'credit' THEN l.total ELSE l.amount END);
        IF l.line_type = 'plan' OR l.line_type = 'usage' THEN
            v_subtotal := v_subtotal + round(l.amount, 2);
        ELSIF l.line_type = 'tax' THEN
            v_tax := v_tax + round(l.amount, 2);
        ELSIF l.line_type = 'credit' THEN
            v_credit := l.credit_applied;
        END IF;
    END LOOP;

    v_total := round(v_subtotal + v_tax - v_credit, 2);
    UPDATE invoices
       SET subtotal = round(v_subtotal, 2), tax = round(v_tax, 2), total = v_total
     WHERE id = v_invoice_id;

    -- Burn down credit notes oldest-first (quirks preserved verbatim).
    FOR r IN SELECT id, remaining_amount FROM credit_notes
              WHERE tenant_id = p_tenant_id AND remaining_amount > 0
              ORDER BY issued_on, id
    LOOP
        EXIT WHEN v_credit <= 0;
        UPDATE credit_notes
           SET remaining_amount = GREATEST(remaining_amount - v_credit, 0)
         WHERE id = r.id;
        v_credit := GREATEST(v_credit - r.remaining_amount, 0);
    END LOOP;

    CALL pkg_ow_util.log_msg('INVOICING', concat('issued invoice=', v_invoice_id,
        ' total=', pkg_ow_util.f_num2char(coalesce(v_total, 0))));
END
$$;

-- ---------------------------------------------------------------------------
-- pkg_dunning
-- ---------------------------------------------------------------------------

CREATE FUNCTION pkg_dunning.fn_overdue_accounts(p_as_of date)
RETURNS TABLE (tenant_id varchar, invoice_id varchar, total numeric,
               days_overdue integer, tenant_status text)
LANGUAGE sql STABLE SET search_path = ow_billing, public AS $$
    SELECT i.tenant_id, i.id, i.total,
           p_as_of - i.issued_at::date,
           CASE t.status_cd WHEN 10 THEN 'active' WHEN 20 THEN 'suspended'
                            ELSE 'UNKNOWN' END
      FROM invoices i
      LEFT JOIN tenants t ON t.id = i.tenant_id
     WHERE i.status_cd = 40
       AND i.issued_at::date < p_as_of
     ORDER BY i.issued_at, i.id
$$;

CREATE PROCEDURE pkg_dunning.sp_schedule_dunning(p_as_of date)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    inv       record;
    v_attempt integer;
    v_next    date;
    v_count   integer := 0;
BEGIN
    FOR inv IN SELECT id, tenant_id FROM invoices
                WHERE status_cd = 40
                ORDER BY issued_at, id
    LOOP
        SELECT coalesce(max(attempt_no), 0) + 1 INTO v_attempt
          FROM dunning_attempts WHERE invoice_id = inv.id;
        -- Saturday -> Monday, Sunday -> Monday.
        v_next := p_as_of + CASE extract(isodow FROM p_as_of)
                              WHEN 6 THEN 2 WHEN 7 THEN 1 ELSE 0 END;
        BEGIN
            INSERT INTO dunning_attempts (id, tenant_id, invoice_id, attempt_no,
                                          scheduled_for, status_cd)
            VALUES (pkg_ow_util.f_md5_uuid(concat(inv.id, v_attempt::text)),
                    inv.tenant_id, inv.id, v_attempt, v_next, 10);
            v_count := v_count + 1;
        EXCEPTION
            -- Oracle swallowed everything here; so does the port.
            WHEN OTHERS THEN NULL;
        END;
    END LOOP;
    CALL pkg_ow_util.log_msg('DUNNING', concat('scheduled ', v_count,
        ' attempts as of ', to_char(p_as_of, 'DD-MON-YY')));
END
$$;

CREATE PROCEDURE pkg_dunning.sp_suspend_overdue(p_as_of date)
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
DECLARE
    t record;
BEGIN
    FOR t IN SELECT DISTINCT i.tenant_id FROM invoices i
              WHERE i.status_cd = 40
                AND i.issued_at::date <= p_as_of - 14
              ORDER BY i.tenant_id
    LOOP
        IF EXISTS (SELECT 1 FROM tenants WHERE id = t.tenant_id AND status_cd = 10) THEN
            UPDATE tenants SET status_cd = 20 WHERE id = t.tenant_id;
            UPDATE subscriptions
               SET status_cd = 20, suspended_on = p_as_of
             WHERE tenant_id = t.tenant_id AND status_cd = 10;
            INSERT INTO notifications (id, tenant_id, kind_cd, sent_at)
            SELECT pkg_ow_util.f_md5_uuid(concat(t.tenant_id, 'suspension',
                                                 to_char(p_as_of, 'YYYY-MM-DD'))),
                   t.tenant_id, 3, p_as_of::timestamp
             WHERE NOT EXISTS (
                   SELECT 1 FROM notifications
                    WHERE tenant_id = t.tenant_id AND kind_cd = 3
                      AND sent_at = p_as_of::timestamp);
            CALL pkg_ow_util.log_msg('DUNNING', concat('suspended tenant=', t.tenant_id));
        END IF;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------------
-- pkg_jobs: bodies of the Oracle DBMS_SCHEDULER jobs (created DISABLED in
-- Oracle). There is no scheduler in this container; call them from cron or
-- an orchestrator if they are ever re-enabled.
-- ---------------------------------------------------------------------------

CREATE PROCEDURE pkg_jobs.job_nightly_dunning()
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    CALL pkg_dunning.sp_schedule_dunning(current_date);
    CALL pkg_dunning.sp_suspend_overdue(current_date);
END
$$;

CREATE PROCEDURE pkg_jobs.job_purge_audit_log()
LANGUAGE plpgsql SET search_path = ow_billing, public AS $$
BEGIN
    DELETE FROM billing_audit_log WHERE logged_at < LOCALTIMESTAMP(0) - interval '90 days';
EXCEPTION
    WHEN OTHERS THEN NULL;
END
$$;
