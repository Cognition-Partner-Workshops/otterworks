/*
  usp_rate_overage
  Rates storage over the plan allowance for each tenant's daily storage row.
  2017-06  mkowalski  created
  2017-08  mkowalski  per-GB rate from dim_plan instead of the old flat rate
*/
CREATE OR ALTER PROCEDURE dbo.usp_rate_overage
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int, @rows_read int;
    DECLARE @tenant_id varchar(36), @bytes_used bigint, @included_bytes bigint, @rate int;
    DECLARE @overage_gb int, @overage_cents int;
    SET @rows = 0;
    SET @rows_read = 0;

    EXEC dbo.usp_log_run @object_name = 'usp_rate_overage', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    UPDATE fact.fact_storage_usage_daily
       SET overage_gb = NULL, overage_cents = NULL
     WHERE business_date = @business_date;

    DECLARE overage_cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT f.tenant_id, f.bytes_used, f.included_bytes, p.overage_cents_per_gb
          FROM fact.fact_storage_usage_daily f
          JOIN dim.dim_plan p ON p.plan_id = f.plan_id
         WHERE f.business_date = @business_date;

    OPEN overage_cur;
    FETCH NEXT FROM overage_cur INTO @tenant_id, @bytes_used, @included_bytes, @rate;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @rows_read = @rows_read + 1;

        IF @bytes_used > @included_bytes
            SET @overage_gb = (@bytes_used - @included_bytes) / 1073741824;
        ELSE
            SET @overage_gb = 0;

        SET @overage_cents = @overage_gb * @rate;

        UPDATE fact.fact_storage_usage_daily
           SET overage_gb = @overage_gb,
               overage_cents = @overage_cents
         WHERE business_date = @business_date
           AND tenant_id = @tenant_id;
        SET @rows = @rows + @@ROWCOUNT;

        FETCH NEXT FROM overage_cur INTO @tenant_id, @bytes_used, @included_bytes, @rate;
    END
    CLOSE overage_cur;
    DEALLOCATE overage_cur;

    EXEC dbo.usp_log_run @object_name = 'usp_rate_overage', @business_date = @business_date, @status = 'succeeded', @rows_read = @rows_read, @rows_written = @rows, @run_id = @run_id;
END
GO
