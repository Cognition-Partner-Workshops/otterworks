/*
  usp_load_dim_plan
  Rebuilds the plan dimension from the billing extract. Seat limits come from
  the price book, which never made it into the billing database.
  2016-03  dkessler   created
  2017-06  mkowalski  included_bytes and per-GB rate from the package
  2019-01  tnguyen    scale tier seat limit raised to 250
*/
CREATE OR ALTER PROCEDURE dbo.usp_load_dim_plan
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_plan', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM dim.dim_plan;

    INSERT INTO dim.dim_plan
        (plan_id, plan_code, plan_tier, monthly_fee_cents, included_units, included_bytes,
         overage_cents_per_gb, seat_limit, is_active, loaded_at)
    SELECT p.id,
           p.code,
           p.tier,
           CAST(p.monthly_fee * 100 AS int),
           p.included_units,
           p.included_bytes,
           p.overage_cents_per_gb,
           CASE p.tier
                WHEN 'starter' THEN 25
                WHEN 'growth'  THEN 75
                WHEN 'scale'   THEN 250
                ELSE 0
           END,
           p.active,
           GETDATE()
      FROM stg.stg_billing_plans p;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_plan', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
