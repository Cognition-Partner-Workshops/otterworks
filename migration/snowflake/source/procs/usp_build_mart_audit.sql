/*
  usp_build_mart_audit
  Audit events counted per tenant, action and resource type for the day.
  2016-06  dkessler   created
*/
CREATE OR ALTER PROCEDURE dbo.usp_build_mart_audit
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_audit', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM mart.mart_audit_rollup WHERE business_date = @business_date;

    INSERT INTO mart.mart_audit_rollup
        (business_date, tenant_id, action, resource_type, event_count, distinct_users, first_event_utc, last_event_utc, loaded_at)
    SELECT @business_date, a.tenant_id, a.action, a.resource_type, COUNT(*), COUNT(DISTINCT a.user_id),
           MIN(a.event_ts_utc), MAX(a.event_ts_utc), GETDATE()
      FROM fact.fact_audit_events a
     WHERE a.business_date = @business_date
     GROUP BY a.tenant_id, a.action, a.resource_type;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_audit', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
