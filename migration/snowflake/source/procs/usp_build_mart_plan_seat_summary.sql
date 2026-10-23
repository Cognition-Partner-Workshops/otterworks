/*
  usp_build_mart_plan_seat_summary
  Seats and seat limits rolled up by plan tier.
  2016-08  dkessler   created
*/
CREATE OR ALTER PROCEDURE dbo.usp_build_mart_plan_seat_summary
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_plan_seat_summary', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM mart.mart_plan_seat_summary WHERE business_date = @business_date;

    INSERT INTO mart.mart_plan_seat_summary
        (business_date, plan_tier, tenant_count, seat_count, seat_limit_total, tenants_over_limit,
         avg_seats_per_tenant, loaded_at)
    SELECT @business_date,
           f.plan_tier,
           COUNT(*),
           SUM(f.seat_count),
           SUM(ISNULL(f.seat_limit, 0)),
           SUM(CASE WHEN f.over_limit = 1 THEN 1 ELSE 0 END),
           CAST(SUM(f.seat_count) AS decimal(10, 2)) / COUNT(*),
           GETDATE()
      FROM fact.fact_seat_assignments f
     WHERE f.business_date = @business_date
       AND f.plan_tier IS NOT NULL
     GROUP BY f.plan_tier;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_build_mart_plan_seat_summary', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
