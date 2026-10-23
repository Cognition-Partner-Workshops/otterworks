/*
  usp_purge_expired
  Weekly housekeeping: trims the run log and agent history older than
  @retention_days, and fact rows for business dates past the same window.
  2016-05  dkessler   created
  2018-02  tnguyen    batch the deletes, the log got too big for one transaction
*/
CREATE OR ALTER PROCEDURE dbo.usp_purge_expired
    @retention_days int = 400
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @cutoff date, @rows int, @total int;
    SET @cutoff = CAST(DATEADD(day, -@retention_days, GETDATE()) AS date);
    SET @total = 0;

    EXEC dbo.usp_log_run @object_name = 'usp_purge_expired', @status = 'started', @run_id = @run_id OUTPUT;

    SET @rows = 1;
    WHILE @rows > 0
    BEGIN
        DELETE TOP (5000) FROM ops.etl_run_log WHERE started_at < @cutoff AND run_id <> @run_id;
        SET @rows = @@ROWCOUNT;
        SET @total = @total + @rows;
    END

    SET @rows = 1;
    WHILE @rows > 0
    BEGIN
        DELETE TOP (5000) FROM ops.agent_job_history WHERE run_date < CONVERT(int, CONVERT(char(8), @cutoff, 112));
        SET @rows = @@ROWCOUNT;
        SET @total = @total + @rows;
    END

    DELETE FROM fact.fact_usage_events WHERE business_date < @cutoff;
    SET @total = @total + @@ROWCOUNT;
    DELETE FROM fact.fact_audit_events WHERE business_date < @cutoff;
    SET @total = @total + @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_purge_expired', @status = 'succeeded', @rows_written = @total, @run_id = @run_id;
END
GO
