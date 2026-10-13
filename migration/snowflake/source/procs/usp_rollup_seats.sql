/*
  usp_rollup_seats
  Seats in use per tenant for the business date.
  2016-05  dkessler   created
  2017-02  dkessler   count from workspace membership so invited users show up
*/
CREATE OR ALTER PROCEDURE dbo.usp_rollup_seats
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_seats', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_seat_assignments WHERE business_date = @business_date;

    INSERT INTO fact.fact_seat_assignments
        (business_date, tenant_id, plan_id, plan_tier, seat_count, seat_limit, over_limit, loaded_at)
    SELECT @business_date,
           t.tenant_id,
           t.plan_id,
           t.plan_tier,
           COUNT(*),
           NULL,
           NULL,
           GETDATE()
      FROM dim.dim_user u
      JOIN stg.stg_auth_workspace_members m ON m.user_id = u.user_id
      JOIN dim.dim_tenant t ON t.tenant_id = m.tenant_id
     WHERE m.joined_at < DATEADD(day, 1, @business_date)
     GROUP BY t.tenant_id, t.plan_id, t.plan_tier;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_seats', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
