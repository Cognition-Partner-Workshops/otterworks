/*
  usp_load_dim_tenant
  One row per billing tenant with the plan they were on for the business date.
  2016-03  dkessler   created
  2017-09  mkowalski  region from the account-ops sheet
*/
CREATE OR ALTER PROCEDURE dbo.usp_load_dim_tenant
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int, @rows_read int;
    DECLARE @tenant_id varchar(36), @name nvarchar(200), @status varchar(20), @tax_exempt bit, @region varchar(20);
    DECLARE @plan_id varchar(36), @plan_tier varchar(20), @sub_status varchar(20);
    SET @rows = 0;
    SET @rows_read = 0;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_tenant', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM dim.dim_tenant;

    DECLARE tenant_cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT id, name, status, tax_exempt, region_code
          FROM stg.stg_billing_tenants
         ORDER BY id;

    OPEN tenant_cur;
    FETCH NEXT FROM tenant_cur INTO @tenant_id, @name, @status, @tax_exempt, @region;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @rows_read = @rows_read + 1;
        SET @plan_id = NULL;
        SET @plan_tier = NULL;
        SET @sub_status = NULL;

        SELECT TOP 1 @plan_id = s.plan_id, @sub_status = s.status
          FROM stg.stg_billing_subscriptions s
         WHERE s.tenant_id = @tenant_id
           AND s.starts_on <= @business_date
           AND (s.ends_on IS NULL OR s.ends_on >= @business_date)
         ORDER BY s.starts_on DESC;

        SELECT @plan_tier = plan_tier FROM dim.dim_plan WHERE plan_id = @plan_id;

        INSERT INTO dim.dim_tenant
            (tenant_id, tenant_name, status, tax_exempt, region_code, plan_id, plan_tier, subscription_status, loaded_at)
        VALUES
            (@tenant_id, @name, @status, @tax_exempt, @region, @plan_id, @plan_tier, @sub_status, GETDATE());
        SET @rows = @rows + 1;

        FETCH NEXT FROM tenant_cur INTO @tenant_id, @name, @status, @tax_exempt, @region;
    END
    CLOSE tenant_cur;
    DEALLOCATE tenant_cur;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_tenant', @business_date = @business_date, @status = 'succeeded', @rows_read = @rows_read, @rows_written = @rows, @run_id = @run_id;
END
GO
