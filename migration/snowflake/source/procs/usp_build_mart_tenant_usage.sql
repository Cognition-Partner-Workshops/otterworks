/*
  usp_build_mart_tenant_usage
  One row per tenant per day for the usage pages and the tenant usage reports.
  2016-08  dkessler   created
  2018-06  tnguyen    document and file counts for the content panel
*/
CREATE OR ALTER PROCEDURE dbo.usp_build_mart_tenant_usage
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;
    DECLARE @tenant_id varchar(36), @tenant_name nvarchar(200), @plan_tier varchar(20), @region varchar(20);
    DECLARE @api int, @compute int, @peak_mb int, @bytes bigint, @users int, @docs int, @files int;
    SET @rows = 0;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_tenant_usage', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM mart.mart_tenant_usage_daily WHERE business_date = @business_date;

    DECLARE tenant_cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT tenant_id, tenant_name, plan_tier, region_code
          FROM dim.dim_tenant
         ORDER BY tenant_name;

    OPEN tenant_cur;
    FETCH NEXT FROM tenant_cur INTO @tenant_id, @tenant_name, @plan_tier, @region;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SELECT @api = ISNULL(SUM(units), 0) FROM fact.fact_usage_events
         WHERE business_date = @business_date AND tenant_id = @tenant_id AND event_kind = 'api';

        SELECT @compute = ISNULL(SUM(units), 0) FROM fact.fact_usage_events
         WHERE business_date = @business_date AND tenant_id = @tenant_id AND event_kind = 'compute';

        SET @peak_mb = 0;
        SET @bytes = 0;
        SELECT @peak_mb = peak_storage_mb, @bytes = bytes_used FROM fact.fact_storage_usage_daily
         WHERE business_date = @business_date AND tenant_id = @tenant_id;

        SELECT @users = COUNT(DISTINCT user_id) FROM fact.fact_audit_events
         WHERE business_date = @business_date AND tenant_id = @tenant_id;

        SELECT @docs = COUNT(*) FROM dim.dim_document WHERE tenant_id = @tenant_id AND is_deleted = 0;

        SELECT @files = COUNT(*) FROM dim.dim_file WHERE tenant_id = @tenant_id AND is_trashed = 0;

        INSERT INTO mart.mart_tenant_usage_daily
            (business_date, tenant_id, tenant_name, plan_tier, region_code, api_units, compute_units,
             storage_peak_mb, bytes_used, active_users, document_count, file_count, loaded_at)
        VALUES
            (@business_date, @tenant_id, @tenant_name, @plan_tier, @region, @api, @compute,
             @peak_mb, @bytes, @users, @docs, @files, GETDATE());
        SET @rows = @rows + 1;

        FETCH NEXT FROM tenant_cur INTO @tenant_id, @tenant_name, @plan_tier, @region;
    END
    CLOSE tenant_cur;
    DEALLOCATE tenant_cur;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_tenant_usage', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
