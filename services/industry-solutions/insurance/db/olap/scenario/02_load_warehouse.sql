-- Month-end scenario, step 2 of 3 (run as COMMISSION_DW against FREEPDB1,
-- after 01_month_end_ledger.sql): full ETL load of every ledger period, then a
-- COMPLETE refresh of the summary materialized view, then reconciliation.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON SIZE UNLIMITED
SET DEFINE OFF
SET FEEDBACK OFF

DECLARE
    g_failures PLS_INTEGER := 0;
    l_merged   PLS_INTEGER;
    l_num      NUMBER;
    l_num2     NUMBER;

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
BEGIN
    dw_etl_pkg.load_commission_facts(NULL, l_merged);
    DBMS_OUTPUT.PUT_LINE('load_commission_facts(NULL): merged ' || l_merged || ' fact rows');
    DBMS_MVIEW.REFRESH('MV_AGENT_COMMISSION_SUMMARY', 'C');
    DBMS_OUTPUT.PUT_LINE('MV_AGENT_COMMISSION_SUMMARY: complete refresh done');

    SELECT COUNT(*) INTO l_num FROM fact_commission;
    SELECT COUNT(*) INTO l_num2 FROM commission_pay.commission_ledger;
    check_case('W1 fact rows match ledger rows', l_num = l_num2, 'fact=' || l_num || ' ledger=' || l_num2);

    SELECT COUNT(*) INTO l_num
      FROM (SELECT period_month, SUM(commission_amt) AS amt
              FROM commission_pay.commission_ledger GROUP BY period_month) l
      FULL JOIN (SELECT period_month, SUM(total_commission) AS amt, SUM(policy_rows) AS n
                   FROM mv_agent_commission_summary GROUP BY period_month) m
        ON m.period_month = l.period_month
     WHERE l.amt IS NULL OR m.amt IS NULL OR l.amt <> m.amt;
    check_case('W2 MV totals reconcile with ledger per period', l_num = 0, 'mismatched periods=' || l_num);

    SELECT COUNT(DISTINCT period_month), COUNT(DISTINCT line_of_business)
      INTO l_num, l_num2 FROM mv_agent_commission_summary;
    check_case('W3 MV covers 12 periods and 4 lines of business', l_num = 12 AND l_num2 = 4,
               'periods=' || l_num || ' lobs=' || l_num2);

    DBMS_OUTPUT.PUT_LINE('----');
    IF g_failures = 0 THEN
        DBMS_OUTPUT.PUT_LINE('SCENARIO WAREHOUSE: ALL PASS');
    ELSE
        DBMS_OUTPUT.PUT_LINE('SCENARIO WAREHOUSE: ' || g_failures || ' FAILURE(S)');
        RAISE_APPLICATION_ERROR(-20099, g_failures || ' scenario check failure(s)');
    END IF;
END;
/

EXIT;
