/*
  usp_rollup_audit
  The day's audit trail, one fact row per audit event.
  2016-06  dkessler   created
  2018-09  tnguyen    runs hourly as well, so it reloads the whole day each time
*/
CREATE OR ALTER PROCEDURE dbo.usp_rollup_audit
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_audit', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_audit_events WHERE business_date = @business_date;

    INSERT INTO fact.fact_audit_events
        (business_date, audit_id, tenant_id, user_id, action, resource_type, resource_id, ip_address, event_ts_utc, loaded_at)
    SELECT @business_date, a.id, a.tenant_id, a.user_id, a.action, a.resource_type, a.resource_id, a.ip_address, a.[timestamp], GETDATE()
      FROM stg.stg_audit_events a
     WHERE a.[timestamp] >= @business_date
       AND a.[timestamp] < DATEADD(day, 1, @business_date);
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_audit', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
