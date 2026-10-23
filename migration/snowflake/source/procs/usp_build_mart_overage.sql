/*
  usp_build_mart_overage
  Storage overage charges per tenant for billing and the overage reports.
  2017-06  mkowalski  created
*/
CREATE OR ALTER PROCEDURE dbo.usp_build_mart_overage
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_overage', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM mart.mart_overage_charges WHERE business_date = @business_date;

    INSERT INTO mart.mart_overage_charges
        (business_date, tenant_id, tenant_name, plan_tier, bytes_used, included_bytes, overage_gb,
         overage_cents_per_gb, overage_cents, loaded_at)
    SELECT f.business_date, f.tenant_id, t.tenant_name, t.plan_tier, f.bytes_used, f.included_bytes, f.overage_gb,
           p.overage_cents_per_gb, f.overage_cents, GETDATE()
      FROM fact.fact_storage_usage_daily f
      JOIN dim.dim_tenant t ON t.tenant_id = f.tenant_id
      JOIN dim.dim_plan p ON p.plan_id = f.plan_id
     WHERE f.business_date = @business_date
       AND f.overage_gb IS NOT NULL;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_overage', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
