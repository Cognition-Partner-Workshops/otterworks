WHENEVER SQLERROR EXIT SQL.SQLCODE

CREATE OR REPLACE PACKAGE dw_policy_claims_pkg AS
    PROCEDURE load_subjects;
END dw_policy_claims_pkg;
/
CREATE OR REPLACE PACKAGE BODY dw_policy_claims_pkg AS
    PROCEDURE load_subjects IS
    BEGIN
        MERGE INTO dim_policy d USING feed_policy s ON (d.pol_id=s.pol_id)
        WHEN MATCHED THEN UPDATE SET d.pol_cd_x=s.pol_cd_x, d.pol_st=s.pol_st, d.ag_cd=s.ag_cd
        WHEN NOT MATCHED THEN INSERT (pol_id, pol_cd_x, pol_st, ag_cd)
            VALUES (s.pol_id, s.pol_cd_x, s.pol_st, s.ag_cd);

        MERGE INTO dim_claim d USING feed_claim s ON (d.clm_id=s.clm_id)
        WHEN MATCHED THEN UPDATE SET d.clm_flg_3=s.clm_flg_3, d.clm_status=s.clm_status
        WHEN NOT MATCHED THEN INSERT (clm_id, pol_id, clm_flg_3, clm_status)
            VALUES (s.clm_id, s.pol_id, s.clm_flg_3, s.clm_status);

        MERGE INTO fact_policy d USING (
            SELECT p.pol_id, p.eff_dt, p.prm_amt, r.rt
              FROM feed_policy p JOIN policy_rate r
                ON r.eff_dt=(SELECT MAX(eff_dt) FROM policy_rate WHERE eff_dt < p.eff_dt)
        ) s ON (d.pol_id=s.pol_id)
        WHEN MATCHED THEN UPDATE SET d.eff_dt=s.eff_dt, d.prm_amt=s.prm_amt, d.rt=s.rt
        WHEN NOT MATCHED THEN INSERT (pol_id, eff_dt, prm_amt, rt)
            VALUES (s.pol_id, s.eff_dt, s.prm_amt, s.rt);

        MERGE INTO fact_claim_payment d USING (
            SELECT clm_id, pay_seq, pay_amt FROM (
                SELECT f.*, ROW_NUMBER() OVER (
                    PARTITION BY clm_id, pay_seq ORDER BY load_ts DESC, pay_amt DESC) rn
                  FROM feed_claim_payment f
            ) WHERE rn=1
        ) s ON (d.clm_id=s.clm_id AND d.pay_seq=s.pay_seq)
        WHEN MATCHED THEN UPDATE SET d.pay_amt=s.pay_amt
        WHEN NOT MATCHED THEN INSERT (clm_id, pay_seq, pay_amt)
            VALUES (s.clm_id, s.pay_seq, s.pay_amt);

        MERGE INTO fact_policy_commission d USING (
            SELECT p.pol_id, a.ag_no, p.ent_cd, a.pct,
                   ROUND(p.c_amt * a.pct / 100, 2)
                       * CASE WHEN p.ent_cd='REVERSAL' THEN -1 ELSE 1 END amt
              FROM feed_policy p JOIN policy_agent_split a ON a.pol_id=p.pol_id
             WHERE p.pol_st <> 'LAPSED' OR p.ent_cd <> 'REVERSAL'
        ) s ON (d.pol_id=s.pol_id AND d.ag_no=s.ag_no AND d.ent_cd=s.ent_cd)
        WHEN MATCHED THEN UPDATE SET d.pct=s.pct, d.commission_amt=s.amt
        WHEN NOT MATCHED THEN INSERT (pol_id, ag_no, ent_cd, pct, commission_amt)
            VALUES (s.pol_id, s.ag_no, s.ent_cd, s.pct, s.amt);
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END load_subjects;
END dw_policy_claims_pkg;
/
BEGIN
    dw_policy_claims_pkg.load_subjects;
END;
/
CREATE OR REPLACE VIEW policy_claim_summary AS
SELECT p.pol_cd_x, c.clm_status, COUNT(*) pay_count, SUM(f.pay_amt) pay_amt
  FROM fact_claim_payment f JOIN dim_claim c ON c.clm_id=f.clm_id
  JOIN dim_policy p ON p.pol_id=c.pol_id
 GROUP BY p.pol_cd_x, c.clm_status;
EXIT;
