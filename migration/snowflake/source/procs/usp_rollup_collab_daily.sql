/*
  usp_rollup_collab_daily
  Comments, live sessions and collaborators per document per day.
  2017-01  mkowalski  created
*/
CREATE OR ALTER PROCEDURE dbo.usp_rollup_collab_daily
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_collab_daily', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_collab_activity_daily WHERE business_date = @business_date;

    INSERT INTO fact.fact_collab_activity_daily
        (business_date, tenant_id, document_id, comment_count, session_count, collaborator_count, loaded_at)
    SELECT @business_date,
           c.tenant_id,
           c.document_id,
           SUM(CASE WHEN c.event_type = 'comment' THEN 1 ELSE 0 END),
           SUM(CASE WHEN c.event_type = 'session_join' THEN 1 ELSE 0 END),
           COUNT(DISTINCT c.user_id),
           GETDATE()
      FROM stg.stg_collab_events c
     WHERE c.created_at >= @business_date
       AND c.created_at < DATEADD(day, 1, @business_date)
       AND c.tenant_id IS NOT NULL
     GROUP BY c.tenant_id, c.document_id;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_collab_daily', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
