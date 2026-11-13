WHENEVER SQLERROR EXIT SQL.SQLCODE
SET VERIFY OFF

CREATE TABLE feed_policy (
    pol_id NUMBER PRIMARY KEY, pol_cd_x VARCHAR2(12), pol_st VARCHAR2(8),
    ag_cd VARCHAR2(16), eff_dt DATE, prm_amt NUMBER(14,4), c_amt NUMBER(14,4),
    ent_cd VARCHAR2(12)
);
CREATE TABLE feed_claim (
    clm_id NUMBER PRIMARY KEY, pol_id NUMBER REFERENCES feed_policy,
    clm_flg_3 NUMBER(1), clm_status NUMBER(1) CHECK (clm_status BETWEEN 1 AND 7),
    loss_dt DATE, report_dt DATE, rsv_amt NUMBER(14,4)
);
CREATE TABLE feed_claim_payment (
    clm_id NUMBER REFERENCES feed_claim, pay_seq NUMBER, pay_amt NUMBER(14,4),
    load_ts TIMESTAMP NOT NULL
);
CREATE TABLE dim_policy (
    pol_id NUMBER PRIMARY KEY, pol_cd_x VARCHAR2(12), pol_st VARCHAR2(8), ag_cd VARCHAR2(16)
);
CREATE TABLE dim_claim (
    clm_id NUMBER PRIMARY KEY, pol_id NUMBER REFERENCES dim_policy,
    clm_flg_3 NUMBER(1), clm_status NUMBER(1) CHECK (clm_status BETWEEN 1 AND 7)
);
CREATE TABLE policy_rate (
    eff_dt DATE PRIMARY KEY, rt NUMBER(8,4) NOT NULL
);
CREATE TABLE policy_agent_split (
    pol_id NUMBER REFERENCES feed_policy, ag_no NUMBER, pct NUMBER(5,2),
    PRIMARY KEY (pol_id, ag_no)
);
CREATE TABLE fact_policy (
    pol_id NUMBER PRIMARY KEY REFERENCES dim_policy, eff_dt DATE,
    prm_amt NUMBER(14,4), rt NUMBER(8,4), ag_cd VARCHAR2(16)
);
CREATE TABLE fact_claim_payment (
    clm_id NUMBER REFERENCES dim_claim, pay_seq NUMBER, pay_amt NUMBER(14,4),
    PRIMARY KEY (clm_id, pay_seq)
);
CREATE TABLE fact_policy_commission (
    pol_id NUMBER REFERENCES dim_policy, ag_no NUMBER, ent_cd VARCHAR2(12),
    pct NUMBER(5,2), commission_amt NUMBER(14,2),
    PRIMARY KEY (pol_id, ag_no, ent_cd)
);

DECLARE
    l_cap PLS_INTEGER := &1;
    l_n PLS_INTEGER;
    l_prm NUMBER;
BEGIN
    IF l_cap < 10 OR l_cap > 200000 THEN
        RAISE_APPLICATION_ERROR(-20041, 'Fact row limit must be between 10 and 200000');
    END IF;
    l_n := FLOOR(l_cap / 5);
    DBMS_RANDOM.SEED(73129);
    INSERT INTO policy_rate VALUES (DATE '2025-01-01', 0.10);
    INSERT INTO policy_rate VALUES (DATE '2025-06-15', 0.12);
    FOR i IN 1..l_n LOOP
        l_prm := 1000 + ROUND(DBMS_RANDOM.VALUE(0, 100), 4);
        INSERT INTO feed_policy VALUES (
            i, 'P' || MOD(i, 9), CASE WHEN MOD(CEIL(i/2),20)=0 THEN 'LAPSED' ELSE 'ACTIVE' END,
            CASE WHEN i <= 6 THEN 'EXT' || i
                 WHEN MOD(i,17)=0 THEN '' ELSE 'AG-' || (100 + MOD(i,6)) END,
            DATE '2025-06-15' + 14.5/24, l_prm,
            CASE WHEN MOD(i,2)=0 THEN 1.00 ELSE 1.01 END,
            CASE WHEN MOD(CEIL(i/2),10)=0 THEN 'REVERSAL' ELSE 'COMMISSION' END);
        INSERT INTO feed_claim VALUES (
            i, i, MOD(i,2), MOD(i-1,7)+1,
            CASE WHEN i <= 3 THEN DATE '1900-01-01'
                 WHEN i <= 6 THEN DATE '2025-07-01' ELSE DATE '2025-06-16' END,
            DATE '2025-06-17', l_prm * 2);
        INSERT INTO feed_claim_payment VALUES (i, 1, 50 + MOD(i,31), TIMESTAMP '2025-06-17 03:00:00');
        IF i <= 8 THEN
            INSERT INTO feed_claim_payment VALUES (i, 1, 49 + MOD(i,31), TIMESTAMP '2025-06-17 02:00:00');
        END IF;
        INSERT INTO policy_agent_split VALUES (i, 1, 33.33);
        INSERT INTO policy_agent_split VALUES (i, 2, 33.33);
        INSERT INTO policy_agent_split VALUES (i, 3, 33.34);
    END LOOP;
    COMMIT;
END;
/
EXIT;
