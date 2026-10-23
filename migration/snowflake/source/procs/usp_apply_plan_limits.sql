/*
  usp_apply_plan_limits
  Stamps the plan seat limit on the day's seat rows and flags tenants over it.
  2016-05  dkessler   created
*/
CREATE OR ALTER PROCEDURE dbo.usp_apply_plan_limits
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_apply_plan_limits', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    UPDATE f
       SET f.seat_limit = p.seat_limit,
           f.over_limit = CASE WHEN f.seat_count > p.seat_limit THEN 1 ELSE 0 END
      FROM fact.fact_seat_assignments f
      JOIN dim.dim_plan p ON p.plan_id = f.plan_id
     WHERE f.business_date = @business_date;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_apply_plan_limits', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
