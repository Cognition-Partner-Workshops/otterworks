-- Warehouse risk probes. Run as COMMISSION_DW after oltp_risk_probes.sql.
SET SERVEROUTPUT ON SIZE UNLIMITED
SET FEEDBACK OFF
DECLARE
    l_m  PLS_INTEGER;
    l_f  NUMBER;
    l_l  NUMBER;
    l_mv NUMBER;
    PROCEDURE say (p VARCHAR2) IS BEGIN DBMS_OUTPUT.PUT_LINE('PROBE ' || p); END;
    PROCEDURE totals IS
    BEGIN
        SELECT NVL(SUM(f.commission_amt), 0) INTO l_f FROM fact_commission f
          JOIN dim_period d ON d.period_key = f.period_key WHERE d.period_month = '2025-06';
        SELECT NVL(SUM(commission_amt), 0) INTO l_l FROM commission_pay.commission_ledger
         WHERE period_month = '2025-06';
        SELECT NVL(SUM(total_commission), 0) INTO l_mv FROM mv_agent_commission_summary
         WHERE period_month = '2025-06';
    END;
BEGIN
    dw_etl_pkg.load_commission_facts('2025-06', l_m);
    DBMS_MVIEW.REFRESH('MV_AGENT_COMMISSION_SUMMARY', 'C');
    totals;
    say('P16a 2025-06 after ETL+refresh (policy 2 still 60/40): fact=' || l_f || ' ledger=' || l_l || ' mv=' || l_mv);
END;
/
-- recalc policy 2 with the new 100/0 split from the OLTP side
CONNECT commission_pay/commission_pay@localhost:1521/FREEPDB1
BEGIN commission_pkg.calculate_policy_commission(2, '2025-06', 'probe'); END;
/
CONNECT commission_dw/commission_dw@localhost:1521/FREEPDB1
SET SERVEROUTPUT ON SIZE UNLIMITED
DECLARE
    l_m  PLS_INTEGER;
    l_f  NUMBER;
    l_l  NUMBER;
    l_mv NUMBER;
    l_n  NUMBER;
    PROCEDURE say (p VARCHAR2) IS BEGIN DBMS_OUTPUT.PUT_LINE('PROBE ' || p); END;
    PROCEDURE totals IS
    BEGIN
        SELECT NVL(SUM(f.commission_amt), 0) INTO l_f FROM fact_commission f
          JOIN dim_period d ON d.period_key = f.period_key WHERE d.period_month = '2025-06';
        SELECT NVL(SUM(commission_amt), 0) INTO l_l FROM commission_pay.commission_ledger
         WHERE period_month = '2025-06';
        SELECT NVL(SUM(total_commission), 0) INTO l_mv FROM mv_agent_commission_summary
         WHERE period_month = '2025-06';
    END;
BEGIN
    dw_etl_pkg.load_commission_facts('2025-06', l_m);
    totals;
    say('P17 after recalc + ETL, before MV refresh: fact=' || l_f || ' ledger=' || l_l || ' mv=' || l_mv
        || ' (MV is stale until someone refreshes it)');
    DBMS_MVIEW.REFRESH('MV_AGENT_COMMISSION_SUMMARY', 'C');
    totals;
    SELECT COUNT(*) INTO l_n FROM fact_commission f JOIN dim_agent a ON a.agent_key = f.agent_key
      JOIN dim_period d ON d.period_key = f.period_key
     WHERE f.policy_id = 2 AND a.agent_id = 2 AND d.period_month = '2025-06';
    say('P16b after refresh: fact=' || l_f || ' ledger=' || l_l || ' mv=' || l_mv
        || '; orphan fact rows for policy 2 / agent 2 = ' || l_n || ' (MERGE never deletes)');
    say('P18 o_rows_merged on the last load=' || l_m || ' (row count of the fact MERGE only)');
END;
/
EXIT;
