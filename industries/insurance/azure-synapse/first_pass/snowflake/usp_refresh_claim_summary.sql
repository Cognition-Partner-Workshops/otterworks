-- dw.usp_refresh_claim_summary: rebuilds per-policy claim totals for the window.
CREATE OR REPLACE PROCEDURE DW.USP_REFRESH_CLAIM_SUMMARY(WINDOW_START DATE, WINDOW_END DATE)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    rc INT;
BEGIN
    TRUNCATE TABLE DW.CLAIM_SUMMARY;
    INSERT INTO DW.CLAIM_SUMMARY (policy_number, product_code, claim_count, total_claim_amount, last_loss_date)
    SELECT p.policy_number, p.product_code, COUNT(*), SUM(c.claim_amount), MAX(c.loss_date)
      FROM STG.CLAIM_FEED c
      JOIN DW.DIM_POLICY p ON UPPER(p.policy_number) = UPPER(c.policy_number)
     WHERE c.loss_date BETWEEN :WINDOW_START AND :WINDOW_END
     GROUP BY p.policy_number, p.product_code;
    rc := SQLROWCOUNT;
    INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected) VALUES ('usp_refresh_claim_summary', 'insert', :rc);
    RETURN 'ok';
EXCEPTION
    WHEN OTHER THEN
        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected)
        VALUES ('usp_refresh_claim_summary', LEFT('error: ' || :SQLERRM, 40), NULL);
        RAISE;
END;
$$;
