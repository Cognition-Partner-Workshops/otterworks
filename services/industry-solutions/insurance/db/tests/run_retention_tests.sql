-- Rate audit retention suite. Run as COMMISSION_PAY after run_audit_tests.sql.
-- The audit rows are written today, so the purge is asked about future
-- dates (p_as_of) rather than backdating rows the guard will not let us edit.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON SIZE UNLIMITED
SET FEEDBACK OFF

DECLARE
    g_failures PLS_INTEGER := 0;
    l_x        NUMBER;   -- HOME-PLUS / agent 3, closed 2020-12-31, no ledger
    l_y        NUMBER;   -- TERM-20 / agent 3, closed 2020-12-31, ledger period 2031-06
    l_n        NUMBER;
    l_n2       NUMBER;
    l_before   NUMBER;
    l_z        NUMBER;
    l_old_log  NUMBER;

    PROCEDURE check_case (p_name IN VARCHAR2, p_ok IN BOOLEAN, p_detail IN VARCHAR2 DEFAULT NULL) IS
    BEGIN
        IF p_ok THEN
            DBMS_OUTPUT.PUT_LINE('PASS ' || p_name);
        ELSE
            g_failures := g_failures + 1;
            DBMS_OUTPUT.PUT_LINE('FAIL ' || p_name || CASE WHEN p_detail IS NOT NULL THEN ' -- ' || p_detail END);
        END IF;
    END check_case;

    FUNCTION trail (p_rate_id IN NUMBER) RETURN NUMBER IS
        l_c NUMBER;
    BEGIN
        SELECT COUNT(*) INTO l_c FROM audit_row_change
         WHERE table_name = 'COMMISSION_RATES' AND row_key = TO_CHAR(p_rate_id);
        RETURN l_c;
    END trail;

    FUNCTION pkg_log (p_product IN VARCHAR2, p_agent IN NUMBER) RETURN NUMBER IS
        l_c NUMBER;
    BEGIN
        SELECT COUNT(*) INTO l_c FROM rate_audit_log
         WHERE product_code = p_product AND NVL(agent_id, -1) = NVL(p_agent, -1)
           AND action IN ('RATE_UPSERT', 'RATE_END');
        RETURN l_c;
    END pkg_log;
BEGIN
    commission_pkg.upsert_commission_rate('HOME-PLUS', 3, 9.00, DATE '2020-01-01', 'ops.lead', l_x);
    commission_pkg.end_commission_rate('HOME-PLUS', 3, DATE '2020-12-31', 'ops.lead');
    commission_pkg.upsert_commission_rate('TERM-20', 3, 14.00, DATE '2020-01-01', 'ops.lead', l_y);
    commission_pkg.end_commission_rate('TERM-20', 3, DATE '2020-12-31', 'ops.lead');
    INSERT INTO commission_ledger (policy_id, agent_id, period_month, rate_id, split_pct, base_premium, commission_amt)
    VALUES (3, 3, '2031-06', l_y, 100, 1200, 168);
    COMMIT;

    ---------------------------------------------------------------
    -- R1: dry run counts and deletes nothing.
    ---------------------------------------------------------------
    SELECT COUNT(*) INTO l_before FROM audit_row_change;
    l_n := rate_retention_pkg.purge(DATE '2034-01-01', 7, TRUE);
    SELECT COUNT(*) INTO l_n2 FROM audit_row_change;
    check_case('R1 dry run counts eligible rows and deletes none',
               l_n >= trail(l_x) + pkg_log('HOME-PLUS', 3) AND l_n2 = l_before AND trail(l_x) = 2,
               'matched=' || l_n || ' before=' || l_before || ' after=' || l_n2);
    SELECT COUNT(*) INTO l_n2 FROM retention_run WHERE dry_run = 'Y' AND rows_purged = 0 AND policy_name = 'rate-audit-7y';
    check_case('R1b dry run logged in retention_run (one row per table)', l_n2 = 2, 'rows=' || l_n2);

    ---------------------------------------------------------------
    -- R2: the period is a parameter; 15 years keeps rate X.
    ---------------------------------------------------------------
    l_n2 := rate_retention_pkg.purge(DATE '2034-01-01', 15, TRUE);
    check_case('R2 longer retention matches fewer rows', l_n2 < l_n, '7y=' || l_n || ' 15y=' || l_n2);
    BEGIN
        l_n2 := rate_retention_pkg.purge(DATE '2034-01-01', 5, TRUE);
        check_case('R2b retention below seven years refused', FALSE);
    EXCEPTION
        WHEN OTHERS THEN check_case('R2b retention below seven years refused', SQLCODE = -20910, SQLERRM);
    END;

    ---------------------------------------------------------------
    -- R3: real run at 2034-01-01 removes the closed rate X; keeps rate Y
    -- (ledger period 2031-06 restarts its clock) and every open rate.
    ---------------------------------------------------------------
    l_before := trail(2);
    l_n := rate_retention_pkg.purge(DATE '2034-01-01', 7, FALSE);
    check_case('R3 closed rate past retention purged from both trails',
               trail(l_x) = 0 AND pkg_log('HOME-PLUS', 3) = 0, 'trail=' || trail(l_x) || ' log=' || pkg_log('HOME-PLUS', 3));
    check_case('R3b rate still inside its ledger clock kept', trail(l_y) = 2 AND pkg_log('TERM-20', 3) = 2,
               'trail=' || trail(l_y) || ' log=' || pkg_log('TERM-20', 3));
    check_case('R3c open rate kept', trail(2) = l_before AND l_before > 0, 'rows=' || trail(2));
    SELECT COUNT(*) INTO l_n2 FROM retention_run WHERE dry_run = 'N' AND rows_purged > 0;
    check_case('R3d real run logged with rows purged', l_n2 >= 1, 'rows=' || l_n2);

    ---------------------------------------------------------------
    -- R4: once the ledger clock has run too (2031-06-30 + 7y), Y goes.
    -- Open rates stay even a century out.
    ---------------------------------------------------------------
    l_n := rate_retention_pkg.purge(DATE '2038-07-01', 7, FALSE);
    check_case('R4 rate purged seven years after its last ledger period', trail(l_y) = 0 AND pkg_log('TERM-20', 3) = 0,
               'trail=' || trail(l_y) || ' log=' || pkg_log('TERM-20', 3));
    l_n := rate_retention_pkg.purge(DATE '2126-01-01', 7, FALSE);
    SELECT COUNT(*), COUNT(CASE WHEN NOT EXISTS (SELECT 1 FROM audit_row_change a
                                                   WHERE a.table_name = 'COMMISSION_RATES'
                                                     AND a.row_key = TO_CHAR(r.rate_id)) THEN 1 END)
      INTO l_n, l_n2
      FROM commission_rates r WHERE r.effective_to IS NULL;
    check_case('R4b open rates never purged', l_n > 0 AND l_n2 = 0, 'open=' || l_n || ' without trail=' || l_n2);

    ---------------------------------------------------------------
    -- R5: the gate is closed again after the purge.
    ---------------------------------------------------------------
    BEGIN
        DELETE FROM audit_row_change WHERE table_name = 'COMMISSION_RATES';
        check_case('R5 direct DELETE refused after a purge', FALSE);
        ROLLBACK;
    EXCEPTION
        WHEN OTHERS THEN check_case('R5 direct DELETE refused after a purge', SQLCODE = -20901, SQLERRM);
    END;

    ---------------------------------------------------------------
    -- R6: a directly deleted rate keeps its scope's package log for
    -- seven years from the DELETE, though it has left commission_rates.
    ---------------------------------------------------------------
    INSERT INTO rate_audit_log (action, product_code, agent_id, detail, actor, logged_at)
    VALUES ('RATE_UPSERT', 'HOME-PLUS', 3, 'r6 old log', 'ops.lead', TIMESTAMP '2015-01-01 00:00:00')
    RETURNING audit_id INTO l_old_log;
    commission_pkg.upsert_commission_rate('HOME-PLUS', 3, 9.50, DATE '2021-01-01', 'ops.lead', l_z);
    DELETE FROM commission_rates WHERE rate_id = l_z;
    COMMIT;
    l_n := rate_retention_pkg.purge(ADD_MONTHS(TRUNC(SYSDATE), 12), 7, FALSE);
    SELECT COUNT(*) INTO l_n2 FROM rate_audit_log WHERE audit_id = l_old_log;
    check_case('R6 deleted rate keeps its scope log for seven years', l_n2 = 1, 'old log rows=' || l_n2);

    DBMS_OUTPUT.PUT_LINE('----');
    IF g_failures = 0 THEN
        DBMS_OUTPUT.PUT_LINE('RETENTION TESTS: ALL PASS');
    ELSE
        DBMS_OUTPUT.PUT_LINE('RETENTION TESTS: ' || g_failures || ' FAILURE(S)');
        RAISE_APPLICATION_ERROR(-20099, g_failures || ' test failure(s)');
    END IF;
END;
/

EXIT;
