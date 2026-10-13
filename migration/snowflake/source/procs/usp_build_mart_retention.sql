/*
  usp_build_mart_retention
  Retention actions counted per tenant, resource type and action.
  2016-09  dkessler   created
*/
CREATE OR ALTER PROCEDURE dbo.usp_build_mart_retention
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_retention', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM mart.mart_retention_summary WHERE business_date = @business_date;

    INSERT INTO mart.mart_retention_summary (business_date, tenant_id, resource_type, retention_action, item_count, loaded_at)
    SELECT @business_date, r.tenant_id, r.resource_type, r.retention_action, COUNT(*), GETDATE()
      FROM fact.fact_retention_actions r
     WHERE r.business_date = @business_date
     GROUP BY r.tenant_id, r.resource_type, r.retention_action;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_retention', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
