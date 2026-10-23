/*
  usp_build_capacity_forecast_input
  The last 28 days of storage peaks per tenant, for the weekly capacity forecast.
  The forecast job writes its numbers back onto the business date rows.
  2018-11  tnguyen    created
*/
CREATE OR ALTER PROCEDURE dbo.usp_build_capacity_forecast_input
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int, @window_start date;
    SET @window_start = DATEADD(day, -27, @business_date);

    EXEC dbo.usp_log_run @object_name = 'usp_build_capacity_forecast_input', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM mart.mart_capacity_forecast_input WHERE business_date = @business_date;

    INSERT INTO mart.mart_capacity_forecast_input
        (business_date, tenant_id, observation_date, plan_tier, peak_storage_mb, bytes_used,
         seat_count, forecast_bytes_30d, forecast_generated_at, loaded_at)
    SELECT @business_date,
           s.tenant_id,
           s.observation_date,
           t.plan_tier,
           s.peak_storage_mb,
           CAST(s.peak_storage_mb AS bigint) * 1048576,
           seats.seat_count,
           NULL,
           NULL,
           GETDATE()
      FROM (SELECT CAST(DATEADD(hour, -4, e.event_ts_utc) AS date) AS observation_date,
                   e.tenant_id,
                   MAX(e.units) AS peak_storage_mb
              FROM stg.stg_billing_usage_events e
             WHERE e.kind = 'storage'
               AND CAST(DATEADD(hour, -4, e.event_ts_utc) AS date) BETWEEN @window_start AND @business_date
             GROUP BY CAST(DATEADD(hour, -4, e.event_ts_utc) AS date), e.tenant_id) s
      LEFT JOIN dim.dim_tenant t ON t.tenant_id = s.tenant_id
      LEFT JOIN fact.fact_seat_assignments seats
             ON seats.tenant_id = s.tenant_id
            AND seats.business_date = @business_date;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_build_capacity_forecast_input', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
