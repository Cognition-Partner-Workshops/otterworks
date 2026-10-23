/*
  usp_rollup_retention
  Works out which documents and files the retention policy acts on.
  Deleted or trashed for 30 days: purge. Archived and untouched for a year: cold storage.
  2016-09  dkessler   created
  2018-03  mkowalski  cold storage for archived content
*/
CREATE OR ALTER PROCEDURE dbo.usp_rollup_retention
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int, @resource_type varchar(20);
    SET @rows = 0;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_retention', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_retention_actions WHERE business_date = @business_date;

    DECLARE type_cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT 'document' UNION ALL SELECT 'file';

    OPEN type_cur;
    FETCH NEXT FROM type_cur INTO @resource_type;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        IF @resource_type = 'document'
        BEGIN
            INSERT INTO fact.fact_retention_actions
                (business_date, tenant_id, resource_type, resource_id, retention_action, days_since_update, loaded_at)
            SELECT @business_date, d.tenant_id, 'document', d.document_id,
                   CASE WHEN d.is_deleted = 1 THEN 'purge' ELSE 'cold_storage' END,
                   DATEDIFF(day, d.updated_at_utc, @business_date),
                   GETDATE()
              FROM dim.dim_document d
             WHERE (d.is_deleted = 1 AND DATEDIFF(day, d.updated_at_utc, @business_date) > 30)
                OR (d.is_deleted = 0 AND d.archived = 1 AND DATEDIFF(day, d.updated_at_utc, @business_date) > 365);
            SET @rows = @rows + @@ROWCOUNT;
        END

        IF @resource_type = 'file'
        BEGIN
            INSERT INTO fact.fact_retention_actions
                (business_date, tenant_id, resource_type, resource_id, retention_action, days_since_update, loaded_at)
            SELECT @business_date, f.tenant_id, 'file', f.file_id,
                   CASE WHEN f.is_trashed = 1 THEN 'purge' ELSE 'cold_storage' END,
                   DATEDIFF(day, f.updated_at_utc, @business_date),
                   GETDATE()
              FROM dim.dim_file f
             WHERE (f.is_trashed = 1 AND DATEDIFF(day, f.updated_at_utc, @business_date) > 30)
                OR (f.is_trashed = 0 AND f.archived = 1 AND DATEDIFF(day, f.updated_at_utc, @business_date) > 365);
            SET @rows = @rows + @@ROWCOUNT;
        END

        FETCH NEXT FROM type_cur INTO @resource_type;
    END
    CLOSE type_cur;
    DEALLOCATE type_cur;

    EXEC dbo.usp_log_run @object_name = 'usp_rollup_retention', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
