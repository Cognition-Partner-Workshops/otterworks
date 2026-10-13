/*
  usp_rollup_storage_daily
  Daily storage peak per tenant from the storage metering samples.
  2016-04  dkessler   created
  2017-06  mkowalski  bytes_used and included_bytes for overage rating
*/
CREATE OR ALTER PROCEDURE dbo.usp_rollup_storage_daily
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_storage_daily', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_storage_usage_daily WHERE business_date = @business_date;

    INSERT INTO fact.fact_storage_usage_daily
        (business_date, tenant_id, plan_id, sample_count, peak_storage_mb, bytes_used,
         included_bytes, overage_gb, overage_cents, loaded_at)
    SELECT s.business_date,
           s.tenant_id,
           t.plan_id,
           s.sample_count,
           s.peak_storage_mb,
           CAST(s.peak_storage_mb AS bigint) * 1048576,
           p.included_bytes,
           NULL,
           NULL,
           GETDATE()
      FROM (SELECT CAST(DATEADD(hour, -4, e.event_ts_utc) AS date) AS business_date,
                   e.tenant_id,
                   COUNT(*)     AS sample_count,
                   MAX(e.units) AS peak_storage_mb
              FROM stg.stg_billing_usage_events e
             WHERE e.kind = 'storage'
               AND CAST(DATEADD(hour, -4, e.event_ts_utc) AS date) = @business_date
             GROUP BY CAST(DATEADD(hour, -4, e.event_ts_utc) AS date), e.tenant_id) s
      LEFT JOIN dim.dim_tenant t ON t.tenant_id = s.tenant_id
      LEFT JOIN dim.dim_plan p ON p.plan_id = t.plan_id;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_storage_daily', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
