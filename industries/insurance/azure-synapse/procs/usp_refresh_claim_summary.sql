-- Rebuilds per-policy claim totals for the window.
CREATE PROCEDURE dw.usp_refresh_claim_summary
    @window_start DATE,
    @window_end   DATE
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        TRUNCATE TABLE dw.claim_summary;

        INSERT INTO dw.claim_summary (policy_number, product_code, claim_count, total_claim_amount, last_loss_date)
        SELECT p.policy_number,
               p.product_code,
               COUNT(*),
               SUM(c.claim_amount),
               MAX(c.loss_date)
          FROM stg.claim_feed c
          JOIN dw.dim_policy p ON p.policy_number = c.policy_number
         WHERE c.loss_date BETWEEN @window_start AND @window_end
         GROUP BY p.policy_number, p.product_code;

        INSERT INTO dw.etl_log (proc_name, step, rows_affected)
        VALUES ('usp_refresh_claim_summary', 'insert', @@ROWCOUNT);
    END TRY
    BEGIN CATCH
        INSERT INTO dw.etl_log (proc_name, step, rows_affected)
        VALUES ('usp_refresh_claim_summary', LEFT('error: ' + ERROR_MESSAGE(), 40), NULL);
        THROW;
    END CATCH
END
GO
