-- Risk probes for the Commission Pay assessment. Run as COMMISSION_PAY on a
-- disposable fixture AFTER both test suites (the procedures commit, so this
-- changes data). Each probe prints PROBE <id> <observation>.
SET SERVEROUTPUT ON SIZE UNLIMITED
SET FEEDBACK OFF
DECLARE
    l_id   NUMBER;
    l_n    NUMBER;
    l_n2   NUMBER;
    l_s    VARCHAR2(400);
    PROCEDURE say (p VARCHAR2) IS BEGIN DBMS_OUTPUT.PUT_LINE('PROBE ' || p); END;
BEGIN
    -- P1/P2: split total check runs on unscaled NUMBER, the column is NUMBER(5,2)
    commission_pkg.set_commission_splits(3,
        split_alloc_tab(split_alloc_t(1, 33.333), split_alloc_t(2, 33.333), split_alloc_t(3, 33.334)), 'probe');
    SELECT SUM(split_pct), LISTAGG(split_pct, '/') WITHIN GROUP (ORDER BY agent_id)
      INTO l_n, l_s FROM commission_splits WHERE policy_id = 3;
    say('P1 input 33.333+33.333+33.334 accepted; stored ' || l_s || ' total=' || l_n);
    commission_pkg.set_commission_splits(3,
        split_alloc_tab(split_alloc_t(1, 33.335), split_alloc_t(2, 33.335), split_alloc_t(3, 33.33)), 'probe');
    SELECT SUM(split_pct), LISTAGG(split_pct, '/') WITHIN GROUP (ORDER BY agent_id)
      INTO l_n, l_s FROM commission_splits WHERE policy_id = 3;
    say('P2 input 33.335+33.335+33.33 accepted; stored ' || l_s || ' total=' || l_n);
    commission_pkg.set_commission_splits(3,
        split_alloc_tab(split_alloc_t(2, 65), split_alloc_t(3, 35)), 'probe');

    -- P3: period format is not validated; '2025-6' becomes its own period key
    commission_pkg.calculate_policy_commission(1, '2025-6', 'probe');
    SELECT COUNT(*) INTO l_n FROM commission_ledger WHERE period_month = '2025-6';
    say('P3 period ''2025-6'' accepted; ledger rows under ''2025-6''=' || l_n);
    DELETE FROM commission_ledger WHERE period_month = '2025-6'; COMMIT;

    -- P4: no check against issued_date (policy 4 issued 2025-05-01)
    commission_pkg.calculate_policy_commission(4, '2024-03', 'probe');
    SELECT COUNT(*), SUM(commission_amt) INTO l_n, l_n2 FROM commission_ledger
     WHERE policy_id = 4 AND period_month = '2024-03';
    say('P4 policy issued 2025-05 calculated for 2024-03: rows=' || l_n || ' amt=' || l_n2);
    DELETE FROM commission_ledger WHERE policy_id = 4 AND period_month = '2024-03'; COMMIT;

    -- P5: back-dating a rate before the open rate's start
    BEGIN
        commission_pkg.upsert_commission_rate('HOME-PLUS', NULL, 9, DATE '2023-06-01', 'probe', l_id);
        say('P5 back-dated rate accepted rate_id=' || l_id);
    EXCEPTION WHEN OTHERS THEN say('P5 back-dated rate rejected with ' || SQLERRM);
    END;

    -- P6/P7: half-up rounding per agent row and penny drift (no remainder allocation)
    INSERT INTO policies (policy_no, product_code, holder_name, annual_premium, issued_date)
    VALUES ('POL-PROBE-0006', 'HOME-PLUS', 'Probe Rounding', 241.20, DATE '2025-01-01')
    RETURNING policy_id INTO l_id;
    COMMIT;
    commission_pkg.set_commission_splits(l_id,
        split_alloc_tab(split_alloc_t(1, 50), split_alloc_t(2, 50)), 'probe');
    commission_pkg.calculate_policy_commission(l_id, '2025-06', 'probe');
    SELECT LISTAGG(commission_amt, '/') WITHIN GROUP (ORDER BY agent_id), SUM(commission_amt)
      INTO l_s, l_n FROM commission_ledger WHERE policy_id = l_id AND period_month = '2025-06';
    say('P6 241.20/12*10%*50% = 1.005 per agent -> stored ' || l_s
        || ' (HALF_EVEN would give 1.00/1.00)');
    say('P7 sum of agent rows=' || l_n || ' vs policy-level ROUND(241.20/12*10%,2)='
        || ROUND(241.20 / 12 * 10 / 100, 2));

    -- P8: same-day amend rewrites a rate row the ledger already points at
    commission_pkg.calculate_policy_commission(3, '2026-02', 'probe');
    SELECT MIN(rate_id), SUM(commission_amt) INTO l_id, l_n FROM commission_ledger
     WHERE policy_id = 3 AND period_month = '2026-02';
    commission_pkg.upsert_commission_rate('TERM-20', NULL, 12, DATE '2024-01-01', 'probe', l_n2);
    SELECT rate_pct INTO l_n2 FROM commission_rates WHERE rate_id = l_id;
    say('P8 ledger 2026-02 policy 3 amt=' || l_n || ' at rate_id=' || l_id
        || '; after same-day amend that rate_id now says ' || l_n2 || '% (ledger not recalculated)');

    -- P9: rate in force at month end applies to the whole month
    commission_pkg.upsert_commission_rate('TERM-20', NULL, 14, DATE '2026-03-15', 'probe', l_id);
    commission_pkg.calculate_policy_commission(3, '2026-03', 'probe');
    SELECT LISTAGG(DISTINCT rate_id, ',') WITHIN GROUP (ORDER BY rate_id), SUM(commission_amt)
      INTO l_s, l_n FROM commission_ledger WHERE policy_id = 3 AND period_month = '2026-03';
    say('P9 rate 14% effective 2026-03-15; 2026-03 used rate_id ' || l_s || ' (new=' || l_id
        || ') for the full month, amt=' || l_n);

    -- P10: a suspended agent already on a split is still paid
    UPDATE agents SET status = 'SUSPENDED' WHERE agent_id = 3; COMMIT;
    commission_pkg.calculate_policy_commission(4, '2025-07', 'probe');
    SELECT COUNT(*) INTO l_n FROM commission_ledger
     WHERE policy_id = 4 AND agent_id = 3 AND period_month = '2025-07';
    say('P10 suspended agent 3 ledger rows for 2025-07=' || l_n);
    UPDATE agents SET status = 'ACTIVE' WHERE agent_id = 3; COMMIT;

    -- P11: the procedures COMMIT or ROLLBACK the caller's transaction
    INSERT INTO rate_audit_log (action, detail, actor) VALUES ('CALLER_WORK', 'uncommitted', 'probe-caller');
    BEGIN
        commission_pkg.upsert_commission_rate('AUTO-STD', NULL, 99, DATE '2026-04-01', 'probe', l_id);
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
    SELECT COUNT(*) INTO l_n FROM rate_audit_log WHERE actor = 'probe-caller';
    say('P11a caller row after a FAILED package call: ' || l_n || ' (rolled back by the package)');
    INSERT INTO rate_audit_log (action, detail, actor) VALUES ('CALLER_WORK', 'uncommitted', 'probe-caller');
    commission_pkg.end_commission_rate('HOME-PLUS', NULL, DATE '2026-12-31', 'probe');
    ROLLBACK;
    SELECT COUNT(*) INTO l_n FROM rate_audit_log WHERE actor = 'probe-caller';
    say('P11b caller row after a SUCCESSFUL package call then caller ROLLBACK: ' || l_n || ' (committed by the package)');

    -- P12: rejected attempts leave no audit row
    SELECT COUNT(*) INTO l_n FROM rate_audit_log;
    BEGIN
        commission_pkg.upsert_commission_rate('AUTO-STD', 4, 9, DATE '2026-05-01', 'probe', l_id);
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
    SELECT COUNT(*) INTO l_n2 FROM rate_audit_log;
    say('P12 audit rows before/after a rejected upsert: ' || l_n || '/' || l_n2);

    -- P13: NULL agent in a split reports as a duplicate
    BEGIN
        commission_pkg.set_commission_splits(3,
            split_alloc_tab(split_alloc_t(NULL, 50), split_alloc_t(2, 50)), 'probe');
        say('P13 NULL agent accepted');
    EXCEPTION WHEN OTHERS THEN say('P13 NULL agent -> ' || SQLERRM);
    END;

    -- P14: end_commission_rate does not validate product or agent
    BEGIN
        commission_pkg.end_commission_rate('NO-SUCH', NULL, DATE '2026-01-01', 'probe');
    EXCEPTION WHEN OTHERS THEN say('P14 unknown product on end_commission_rate -> ' || SQLERRM);
    END;

    -- P15: ux_rates_open keys closed rows as (product, NVL(agent,-1), NULL), which
    -- is still unique, so a scope can hold only one closed rate. AUTO-STD default
    -- already has one closed row (from T1); a further supersede needs a second.
    SELECT COUNT(*) INTO l_n FROM commission_rates
     WHERE product_code = 'AUTO-STD' AND agent_id IS NULL AND effective_to IS NOT NULL;
    BEGIN
        commission_pkg.upsert_commission_rate('AUTO-STD', NULL, 9, DATE '2026-06-01', 'probe', l_id);
        say('P15 second supersede of AUTO-STD default accepted rate_id=' || l_id);
    EXCEPTION WHEN OTHERS THEN
        say('P15 AUTO-STD default has ' || l_n || ' closed row(s); next supersede -> '
            || SUBSTR(SQLERRM, 1, 110));
    END;
END;
/

-- P16: drop agent 2 from policy 2 after its 2025-06 rows reached the warehouse
SET SERVEROUTPUT ON
BEGIN
    commission_pkg.calculate_policy_commission(2, '2025-06', 'probe');
    commission_pkg.set_commission_splits(2, split_alloc_tab(split_alloc_t(1, 100)), 'probe');
    DBMS_OUTPUT.PUT_LINE('PROBE P16 setup: policy 2 calculated with 60/40, then re-split 100/0 (recalc runs from the DW probe)');
END;
/
EXIT;
