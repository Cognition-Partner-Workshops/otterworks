-- OLAP/ETL test suite. Run as COMMISSION_DW against FREEPDB1 AFTER the OLTP
-- suite (it consumes the ledger rows the OLTP tests calculated):
--   sqlplus commission_dw/commission_dw@localhost:1521/FREEPDB1 @run_olap_tests.sql
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET SERVEROUTPUT ON SIZE UNLIMITED
SET FEEDBACK OFF

DECLARE
    g_failures PLS_INTEGER := 0;
    l_merged   PLS_INTEGER;
    l_num      NUMBER;
    l_num2     NUMBER;
    TYPE payment_rows IS TABLE OF feed_claim_payment%ROWTYPE;
    l_payments payment_rows;

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
    ---------------------------------------------------------------
    -- E1: ETL loads the 2025-06 ledger rows into the star schema
    ---------------------------------------------------------------
    dw_etl_pkg.load_commission_facts('2025-06', l_merged);
    check_case('E1 ETL merges fact rows', l_merged >= 3, 'merged=' || l_merged);
    SELECT COUNT(*) INTO l_num FROM fact_commission;
    check_case('E1a fact rows present', l_num >= 3, 'rows=' || l_num);

    ---------------------------------------------------------------
    -- E2: fact totals reconcile with the OLTP ledger for the period
    ---------------------------------------------------------------
    SELECT NVL(SUM(commission_amt), 0) INTO l_num
      FROM fact_commission f
      JOIN dim_period d ON d.period_key = f.period_key
     WHERE d.period_month = '2025-06';
    SELECT NVL(SUM(commission_amt), 0) INTO l_num2
      FROM commission_pay.commission_ledger
     WHERE period_month = '2025-06';
    check_case('E2 fact totals reconcile with ledger', l_num = l_num2,
               'fact=' || l_num || ' ledger=' || l_num2);

    ---------------------------------------------------------------
    -- E3: re-running the ETL is idempotent
    ---------------------------------------------------------------
    SELECT COUNT(*) INTO l_num FROM fact_commission;
    dw_etl_pkg.load_commission_facts('2025-06', l_merged);
    SELECT COUNT(*) INTO l_num2 FROM fact_commission;
    check_case('E3 ETL rerun does not duplicate facts', l_num = l_num2,
               'before=' || l_num || ' after=' || l_num2);

    ---------------------------------------------------------------
    -- E4: the summary materialized view reflects loaded facts
    ---------------------------------------------------------------
    DBMS_MVIEW.REFRESH('MV_AGENT_COMMISSION_SUMMARY', 'C');
    SELECT COUNT(*) INTO l_num FROM mv_agent_commission_summary WHERE period_month = '2025-06';
    check_case('E4 summary MV populated', l_num >= 3, 'rows=' || l_num);

    dw_policy_claims_pkg.load_subjects;
    SELECT COUNT(*) INTO l_num FROM feed_policy;
    SELECT COUNT(*) INTO l_num2 FROM fact_policy;
    check_case('P1 policy count reconciles', l_num > 0 AND l_num=l_num2);
    SELECT COUNT(*) INTO l_num FROM feed_claim;
    SELECT COUNT(*) INTO l_num2 FROM dim_claim;
    check_case('P2 claim count reconciles', l_num=l_num2);
    SELECT COUNT(*) INTO l_num FROM fact_policy WHERE prm_amt <> ROUND(prm_amt,2);
    check_case('P3 premium scale retained', l_num > 0);
    SELECT COUNT(*) INTO l_num FROM dim_policy WHERE ag_cd IS NULL;
    SELECT COUNT(*) INTO l_num2 FROM feed_policy WHERE ag_cd IS NULL;
    check_case('P4 unassigned agents retained', l_num > 0 AND l_num=l_num2);
    SELECT COUNT(*) INTO l_num FROM fact_policy WHERE rt=0.12 AND eff_dt > TRUNC(eff_dt);
    SELECT COUNT(*) INTO l_num2 FROM fact_policy;
    check_case('P5 intraday rate resolution', l_num=l_num2);
    SELECT MAX(rt) INTO l_num FROM policy_rate
     WHERE eff_dt < DATE '2025-06-15';
    check_case('P5a opening boundary rate', l_num=0.10);
    SELECT SUM(pay_amt) INTO l_num FROM fact_claim_payment;
    SELECT SUM(pay_amt) INTO l_num2 FROM (
        SELECT f.*, ROW_NUMBER() OVER (
            PARTITION BY clm_id, pay_seq ORDER BY load_ts DESC, pay_amt DESC) rn
        FROM feed_claim_payment f) WHERE rn=1;
    check_case('P6 latest payment totals reconcile', l_num=l_num2);
    SELECT COUNT(*) INTO l_num FROM feed_claim_payment;
    SELECT COUNT(*) INTO l_num2 FROM fact_claim_payment;
    check_case('P6a payment delivery count', l_num-l_num2=8);
    SELECT COUNT(*) INTO l_num FROM fact_policy_commission f JOIN feed_policy p ON p.pol_id=f.pol_id
     WHERE f.commission_amt <> ROUND(p.c_amt*f.pct/100,2)
           * CASE WHEN p.ent_cd='REVERSAL' THEN -1 ELSE 1 END;
    check_case('P7 agent row amounts reconcile', l_num=0);
    SELECT COUNT(*) INTO l_num FROM (
        SELECT p.pol_id FROM feed_policy p JOIN fact_policy_commission f ON f.pol_id=p.pol_id
        GROUP BY p.pol_id, p.c_amt
        HAVING ABS(SUM(f.commission_amt)) <> ROUND(p.c_amt,2));
    check_case('P7a split distributions present', l_num > 0);
    SELECT SUM(commission_amt) INTO l_num FROM fact_policy_commission;
    SELECT SUM(CASE WHEN ent_cd='REVERSAL' THEN -c_amt ELSE c_amt END) INTO l_num2
      FROM feed_policy WHERE pol_st <> 'LAPSED' OR ent_cd <> 'REVERSAL';
    check_case('P7b portfolio distribution total', ROUND(l_num,2)=ROUND(l_num2,2));
    SELECT COUNT(*) INTO l_num FROM fact_policy_commission f JOIN dim_policy p ON p.pol_id=f.pol_id
     WHERE f.ent_cd='REVERSAL' AND p.pol_st='LAPSED';
    check_case('P8 lapsed reversal eligibility', l_num=0);
    SELECT COUNT(*)*3 INTO l_num FROM feed_policy
     WHERE pol_st <> 'LAPSED' OR ent_cd <> 'REVERSAL';
    SELECT COUNT(*) INTO l_num2 FROM fact_policy_commission;
    check_case('P8a eligible agent row count', l_num=l_num2);
    SELECT COUNT(*) INTO l_num FROM fact_policy_commission WHERE ent_cd='REVERSAL';
    check_case('P8b active reversals loaded', l_num > 0);
    dw_policy_claims_pkg.load_subjects;
    SELECT COUNT(*) INTO l_num FROM fact_policy_commission;
    check_case('P9 subject reload is idempotent', l_num=l_num2);
    SELECT COUNT(*) INTO l_num FROM dim_claim WHERE clm_status BETWEEN 1 AND 7;
    SELECT COUNT(*) INTO l_num2 FROM feed_claim;
    check_case('P10 claim status coverage', l_num=l_num2);

    SELECT * BULK COLLECT INTO l_payments FROM feed_claim_payment;
    SELECT COUNT(*) INTO l_num FROM fact_claim_payment;
    DELETE FROM feed_claim_payment;
    dw_policy_claims_pkg.load_subjects;
    SELECT COUNT(*) INTO l_num2 FROM fact_claim_payment;
    check_case('P11 empty payment delivery retains history', l_num=l_num2);
    FORALL i IN 1..l_payments.COUNT
        INSERT INTO feed_claim_payment VALUES l_payments(i);
    COMMIT;
    BEGIN
        UPDATE feed_claim SET clm_status=8 WHERE clm_id=1;
        check_case('P12 claim status range enforced', FALSE);
        ROLLBACK;
    EXCEPTION
        WHEN OTHERS THEN
            check_case('P12 claim status range enforced', SQLCODE=-2290);
            ROLLBACK;
    END;

    DBMS_OUTPUT.PUT_LINE('----');
    IF g_failures = 0 THEN
        DBMS_OUTPUT.PUT_LINE('OLAP TESTS: ALL PASS');
    ELSE
        DBMS_OUTPUT.PUT_LINE('OLAP TESTS: ' || g_failures || ' FAILURE(S)');
        RAISE_APPLICATION_ERROR(-20099, g_failures || ' test failure(s)');
    END IF;
END;
/

EXIT;
