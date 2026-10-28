-- u-plans routine-parity fixture snapshot, Lakebase database ow_tp branch
-- mig-1793185083, dedicated execution schema mig_1793185083_exec (the committed
-- allowlist admits no other Lakebase branch, so the dedicated exec target is a
-- separate schema on the batch branch; recorded as target_branch
-- "mig-1793185083-exec" in the run records).
--
-- Reproduces the converted subscriptions/subscriptions_hist DDL, sequence,
-- triggers and sp_change_plan at fixture scale, then seeds the input rows every
-- run record in ../runs/ executed against. Re-applying this file resets the
-- fixture byte-for-byte.
--
-- Seed (tenant 't'):
--   sub-open-1     active open subscription  -> sp_change_plan closes it
--   sub-cancelled  cancelled open subscription -> close-out keeps status 30
--   sub-closed     already-ended subscription -> outside the FOR UPDATE cursor

CREATE SCHEMA IF NOT EXISTS mig_1793185083_exec;

DROP TABLE IF EXISTS mig_1793185083_exec.subscriptions;
DROP TABLE IF EXISTS mig_1793185083_exec.subscriptions_hist;
DROP SEQUENCE IF EXISTS mig_1793185083_exec.seq_subscriptions_hist;

CREATE TABLE mig_1793185083_exec.subscriptions (
    id           varchar(36) PRIMARY KEY,
    tenant_id    varchar(36),
    plan_id      varchar(36),
    starts_on    date,
    ends_on      date,
    status_cd    bigint,
    suspended_on date
);

CREATE TABLE mig_1793185083_exec.subscriptions_hist (
    hist_id      bigint PRIMARY KEY,
    hist_dt      text,
    hist_dt_raw  varchar(20),
    hist_op      varchar(3),
    id           varchar(36),
    tenant_id    varchar(36),
    plan_id      varchar(36),
    starts_on    date,
    ends_on      date,
    status_cd    bigint,
    suspended_on date
);

CREATE SEQUENCE mig_1793185083_exec.seq_subscriptions_hist START WITH 1;

CREATE OR REPLACE FUNCTION mig_1793185083_exec.trg_subscriptions_hist_fn()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO mig_1793185083_exec.subscriptions_hist (
        hist_id, hist_dt, hist_dt_raw, hist_op, id, tenant_id, plan_id,
        starts_on, ends_on, status_cd, suspended_on)
    VALUES (
        nextval('mig_1793185083_exec.seq_subscriptions_hist'),
        to_char(now(), 'DD-MON-YY HH24:MI:SS'),
        to_char(now(), 'DD-MON-YY HH24:MI:SS'),
        CASE WHEN TG_OP = 'DELETE' THEN 'DEL' ELSE 'UPD' END,
        OLD.id, OLD.tenant_id, OLD.plan_id,
        OLD.starts_on, OLD.ends_on, OLD.status_cd, OLD.suspended_on);
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_subscriptions_hist ON mig_1793185083_exec.subscriptions;
CREATE TRIGGER trg_subscriptions_hist
    AFTER UPDATE OR DELETE ON mig_1793185083_exec.subscriptions
    FOR EACH ROW EXECUTE FUNCTION mig_1793185083_exec.trg_subscriptions_hist_fn();

CREATE OR REPLACE FUNCTION mig_1793185083_exec.trg_sub_no_uncancel_fn()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status_cd = 30 THEN
        NEW.status_cd := 30;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sub_no_uncancel ON mig_1793185083_exec.subscriptions;
CREATE TRIGGER trg_sub_no_uncancel
    BEFORE UPDATE OF status_cd ON mig_1793185083_exec.subscriptions
    FOR EACH ROW EXECUTE FUNCTION mig_1793185083_exec.trg_sub_no_uncancel_fn();

CREATE OR REPLACE FUNCTION mig_1793185083_exec.sp_change_plan(
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
          FROM mig_1793185083_exec.subscriptions
         WHERE tenant_id = p_tenant_id
           AND ends_on IS NULL
           AND starts_on < p_effective_on
         FOR UPDATE
    LOOP
        UPDATE mig_1793185083_exec.subscriptions
           SET ends_on = p_effective_on - 1,
               status_cd = CASE WHEN r.status_cd = 30 THEN 30 ELSE 10 END
         WHERE id = r.id;
    END LOOP;

    v_md5 := md5(p_tenant_id || p_plan_id || to_char(p_effective_on, 'YYYY-MM-DD'));
    v_new_id := substr(v_md5, 1, 8) || '-' || substr(v_md5, 9, 4) || '-' ||
                substr(v_md5, 13, 4) || '-' || substr(v_md5, 17, 4) || '-' ||
                substr(v_md5, 21, 12);

    INSERT INTO mig_1793185083_exec.subscriptions (id, tenant_id, plan_id, starts_on, status_cd)
    VALUES (v_new_id, p_tenant_id, p_plan_id, p_effective_on, 10);
END;
$$;

INSERT INTO mig_1793185083_exec.subscriptions
    (id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on)
VALUES
    ('sub-open-1', 't', 'p1', DATE '2024-01-01', NULL, 10, NULL),
    ('sub-cancelled', 't', 'p1', DATE '2024-02-01', NULL, 30, NULL),
    ('sub-closed', 't', 'p1', DATE '2024-03-01', DATE '2025-01-01', 10, NULL);
