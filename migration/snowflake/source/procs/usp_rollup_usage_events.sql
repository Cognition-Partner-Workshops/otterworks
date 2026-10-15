/*
  usp_rollup_usage_events
  Copies the day's metered usage events into the fact table.
  2016-04  dkessler   created
*/
CREATE OR ALTER PROCEDURE dbo.usp_rollup_usage_events
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_usage_events', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_usage_events WHERE business_date = @business_date;

    INSERT INTO fact.fact_usage_events (business_date, event_id, tenant_id, event_kind, units, event_ts_utc, loaded_at)
    SELECT @business_date, e.id, e.tenant_id, e.kind, e.units, e.event_ts_utc, GETDATE()
      FROM stg.stg_billing_usage_events e
     WHERE e.event_ts_utc >= @business_date
       AND e.event_ts_utc < DATEADD(day, 1, @business_date);
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_usage_events', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
