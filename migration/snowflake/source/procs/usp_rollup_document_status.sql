/*
  usp_rollup_document_status
  Live documents per workspace split by status, for the content reports.
  2018-03  mkowalski  created
*/
CREATE OR ALTER PROCEDURE dbo.usp_rollup_document_status
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_document_status', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_document_status_daily WHERE business_date = @business_date;

    INSERT INTO fact.fact_document_status_daily
        (business_date, tenant_id, workspace_id, status_label, document_count, word_count, loaded_at)
    SELECT @business_date,
           d.tenant_id,
           d.workspace_id,
           d.status_label,
           COUNT(*),
           SUM(CAST(d.word_count AS bigint)),
           GETDATE()
      FROM (SELECT tenant_id,
                   workspace_id,
                   word_count,
                   CASE WHEN archived = 1 THEN 'archived' ELSE 'active' END AS status_label
              FROM dim.dim_document
             WHERE is_deleted = 0
               AND created_at_utc < DATEADD(day, 1, @business_date)) d
     GROUP BY d.tenant_id, d.workspace_id, d.status_label;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_document_status', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
