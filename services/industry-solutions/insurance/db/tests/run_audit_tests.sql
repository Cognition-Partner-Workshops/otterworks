-- Rate change audit suite (23 NYCRR 500.6 audit trail). Run as COMMISSION_PAY
-- against FREEPDB1 after run_tests.sql:
--   sqlplus commission_pay/commission_pay@localhost:1521/FREEPDB1 @run_audit_tests.sql
-- Every query against the audit objects is dynamic SQL, so the suite also runs
-- (and fails case by case) on a schema that does not have them yet: that is
-- the red run recorded before the trigger existed.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON SIZE UNLIMITED
SET FEEDBACK OFF

VARIABLE t_start VARCHAR2(40)
EXEC :t_start := TO_CHAR(SYSTIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM')

-- The statements under test, sent straight from the client the way someone
-- outside COMMISSION_PKG would run them.
UPDATE commission_rates SET rate_pct = 11.25 WHERE rate_id = 2;
COMMIT;
INSERT INTO commission_rates (product_code, agent_id, rate_pct, effective_from, effective_to, created_by)
VALUES ('TERM-20', 2, 12.00, DATE '2023-01-01', DATE '2023-12-31', 'direct-sql');
DELETE FROM commission_rates WHERE created_by = 'direct-sql';
COMMIT;
EXEC DECLARE l_id NUMBER; BEGIN commission_pkg.upsert_commission_rate('TERM-20', NULL, 16.00, DATE '2026-03-01', 'ops.lead', l_id); END;
UPDATE commission_rates SET rate_pct = 16.50
 WHERE product_code = 'TERM-20' AND agent_id IS NULL AND effective_from = DATE '2026-03-01';
COMMIT;

DECLARE
    g_failures  PLS_INTEGER := 0;
    l_rate_id   NUMBER;
    l_num       NUMBER;
    l_actor     VARCHAR2(400);
    l_via       VARCHAR2(400);
    l_old_pct   NUMBER;
    l_new_pct   NUMBER;
    l_start     TIMESTAMP WITH TIME ZONE := TO_TIMESTAMP_TZ(:t_start, 'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM');
    l_user      VARCHAR2(128) := SYS_CONTEXT('USERENV', 'SESSION_USER');

    PROCEDURE check_case (p_name IN VARCHAR2, p_ok IN BOOLEAN, p_detail IN VARCHAR2 DEFAULT NULL) IS
    BEGIN
        IF p_ok THEN
            DBMS_OUTPUT.PUT_LINE('PASS ' || p_name);
        ELSE
            g_failures := g_failures + 1;
            DBMS_OUTPUT.PUT_LINE('FAIL ' || p_name
                || CASE WHEN p_detail IS NOT NULL THEN ' -- ' || p_detail END);
        END IF;
    END check_case;

    FUNCTION history_count (p_rate_id IN NUMBER, p_op IN VARCHAR2) RETURN NUMBER IS
        l_n NUMBER;
    BEGIN
        EXECUTE IMMEDIATE
            'SELECT COUNT(*) FROM v_rate_change_history
              WHERE rate_id = :r AND operation = :o AND changed_at >= :t'
            INTO l_n USING p_rate_id, p_op, l_start;
        RETURN l_n;
    END history_count;
BEGIN
    ---------------------------------------------------------------
    -- A1: a direct UPDATE outside COMMISSION_PKG is recorded with the
    -- session's database user, the time, and the before/after rate.
    ---------------------------------------------------------------
    BEGIN
        EXECUTE IMMEDIATE
            'SELECT actor, via_program, old_rate_pct, new_rate_pct
               FROM v_rate_change_history
              WHERE rate_id = 2 AND operation = ''UPDATE'' AND changed_at >= :t
              ORDER BY change_id DESC FETCH FIRST 1 ROW ONLY'
            INTO l_actor, l_via, l_old_pct, l_new_pct USING l_start;
        check_case('A1 direct UPDATE records actor, time and old/new rate',
                   l_actor LIKE l_user || '%' AND l_via = 'SQL' AND l_old_pct = 10 AND l_new_pct = 11.25,
                   'actor=' || l_actor || ' via=' || l_via || ' old=' || l_old_pct || ' new=' || l_new_pct);
    EXCEPTION
        WHEN OTHERS THEN
            check_case('A1 direct UPDATE records actor, time and old/new rate', FALSE, SQLERRM);
    END;

    ---------------------------------------------------------------
    -- A1b: before this suite, the only trail was rate_audit_log, which the
    -- package writes; the direct UPDATE above must not depend on it.
    ---------------------------------------------------------------
    SELECT COUNT(*) INTO l_num FROM rate_audit_log
     WHERE logged_at >= CAST(l_start AS TIMESTAMP) AND product_code = 'HOME-PLUS';
    check_case('A1b direct UPDATE writes no package audit row (trail is the trigger)', l_num = 0, 'rows=' || l_num);

    ---------------------------------------------------------------
    -- A2: a direct INSERT and DELETE are recorded.
    ---------------------------------------------------------------
    BEGIN
        EXECUTE IMMEDIATE
            'SELECT MAX(rate_id) FROM v_rate_change_history WHERE created_by = ''direct-sql'' AND changed_at >= :t'
            INTO l_rate_id USING l_start;
        check_case('A2 direct INSERT recorded', history_count(l_rate_id, 'INSERT') = 1);
        check_case('A2b direct DELETE recorded', history_count(l_rate_id, 'DELETE') = 1);
    EXCEPTION
        WHEN OTHERS THEN
            check_case('A2 direct INSERT/DELETE recorded', FALSE, SQLERRM);
    END;

    ---------------------------------------------------------------
    -- A3: a change through the package carries the package's p_actor and
    -- names the package procedure that issued the DML.
    ---------------------------------------------------------------
    SELECT rate_id INTO l_rate_id FROM commission_rates
     WHERE product_code = 'TERM-20' AND agent_id IS NULL AND effective_from = DATE '2026-03-01';
    BEGIN
        EXECUTE IMMEDIATE
            'SELECT actor, via_program FROM v_rate_change_history
              WHERE rate_id = :r AND operation = ''INSERT'' AND changed_at >= :t'
            INTO l_actor, l_via USING l_rate_id, l_start;
        check_case('A3 package change carries p_actor and the issuing procedure',
                   l_actor = 'ops.lead' AND l_via = 'COMMISSION_PKG.UPSERT_COMMISSION_RATE',
                   'actor=' || l_actor || ' via=' || l_via);
        EXECUTE IMMEDIATE
            'SELECT COUNT(*) FROM v_rate_change_history
              WHERE rate_id = 3 AND operation = ''UPDATE'' AND actor = ''ops.lead'' AND changed_at >= :t'
            INTO l_num USING l_start;
        check_case('A3b superseded rate closed by the package is attributed too', l_num = 1, 'rows=' || l_num);
    EXCEPTION
        WHEN OTHERS THEN
            check_case('A3 package change carries p_actor and the issuing procedure', FALSE, SQLERRM);
    END;

    ---------------------------------------------------------------
    -- A4: a stale package actor does not leak onto a later direct UPDATE in
    -- the same session.
    ---------------------------------------------------------------
    BEGIN
        EXECUTE IMMEDIATE
            'SELECT actor, via_program FROM v_rate_change_history
              WHERE rate_id = :r AND operation = ''UPDATE'' AND changed_at >= :t
              ORDER BY change_id DESC FETCH FIRST 1 ROW ONLY'
            INTO l_actor, l_via USING l_rate_id, l_start;
        check_case('A4 later direct UPDATE is not attributed to the package actor',
                   l_actor LIKE l_user || '%' AND l_via = 'SQL', 'actor=' || l_actor || ' via=' || l_via);
    EXCEPTION
        WHEN OTHERS THEN
            check_case('A4 later direct UPDATE is not attributed to the package actor', FALSE, SQLERRM);
    END;

    ---------------------------------------------------------------
    -- A5: the view answers "who changed rate X and when" in one row per
    -- change: rate 2 has its baseline row plus exactly one change.
    ---------------------------------------------------------------
    BEGIN
        EXECUTE IMMEDIATE
            'SELECT COUNT(*), COUNT(DISTINCT change_id) FROM v_rate_change_history WHERE rate_id = 2'
            INTO l_num, l_new_pct;
        check_case('A5 one row per change for rate 2 (baseline + 1 update)', l_num = 2 AND l_new_pct = 2,
                   'rows=' || l_num || ' distinct=' || l_new_pct);
    EXCEPTION
        WHEN OTHERS THEN
            check_case('A5 one row per change for rate 2 (baseline + 1 update)', FALSE, SQLERRM);
    END;

    ---------------------------------------------------------------
    -- A6: the change log is append-only for the schema owner.
    ---------------------------------------------------------------
    BEGIN
        EXECUTE IMMEDIATE 'UPDATE audit_row_change SET app_actor = ''forged'' WHERE table_name = ''COMMISSION_RATES''';
        check_case('A6 UPDATE on the change log is refused', FALSE, 'update succeeded');
        ROLLBACK;
    EXCEPTION
        WHEN OTHERS THEN
            check_case('A6 UPDATE on the change log is refused', SQLCODE = -20901, SQLERRM);
    END;
    BEGIN
        EXECUTE IMMEDIATE 'DELETE FROM audit_row_change WHERE table_name = ''COMMISSION_RATES''';
        check_case('A6b DELETE on the change log is refused', FALSE, 'delete succeeded');
        ROLLBACK;
    EXCEPTION
        WHEN OTHERS THEN
            check_case('A6b DELETE on the change log is refused', SQLCODE = -20901, SQLERRM);
    END;

    DBMS_OUTPUT.PUT_LINE('----');
    IF g_failures = 0 THEN
        DBMS_OUTPUT.PUT_LINE('AUDIT TESTS: ALL PASS');
    ELSE
        DBMS_OUTPUT.PUT_LINE('AUDIT TESTS: ' || g_failures || ' FAILURE(S)');
        RAISE_APPLICATION_ERROR(-20099, g_failures || ' test failure(s)');
    END IF;
END;
/

EXIT;
