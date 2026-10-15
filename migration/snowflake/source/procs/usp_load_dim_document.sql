/*
  usp_load_dim_document
  Documents with their version count, rebuilt in full each night.
  2016-05  dkessler   created
  2018-03  mkowalski  archived flag from document-service
*/
CREATE OR ALTER PROCEDURE dbo.usp_load_dim_document
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_document', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM dim.dim_document;

    INSERT INTO dim.dim_document
        (document_id, tenant_id, workspace_id, owner_id, title, content_type, is_deleted, is_template,
         archived, word_count, version_count, created_at_utc, updated_at_utc, loaded_at)
    SELECT d.id, d.tenant_id, d.workspace_id, d.owner_id, d.title, d.content_type, d.is_deleted, d.is_template,
           d.archived, d.word_count, ISNULL(v.version_count, 0), d.created_at, d.updated_at, GETDATE()
      FROM stg.stg_documents d
      LEFT JOIN (SELECT document_id, COUNT(*) AS version_count
                   FROM stg.stg_document_versions
                  GROUP BY document_id) v ON v.document_id = d.id
     WHERE d.created_at < DATEADD(day, 1, @business_date);
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_document', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
