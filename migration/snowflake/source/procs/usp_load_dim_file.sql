/*
  usp_load_dim_file
  Files with their version count, rebuilt in full each night.
  2016-05  dkessler   created
  2018-03  mkowalski  archived flag from file-service
*/
CREATE OR ALTER PROCEDURE dbo.usp_load_dim_file
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_file', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM dim.dim_file;

    INSERT INTO dim.dim_file
        (file_id, tenant_id, workspace_id, owner_id, file_name, mime_type, size_bytes, size_mb, is_trashed,
         archived, version_count, created_at_utc, updated_at_utc, loaded_at)
    SELECT f.id, f.tenant_id, f.workspace_id, f.owner_id, f.name, f.mime_type, f.size_bytes, f.size_mb, f.is_trashed,
           f.archived, ISNULL(v.version_count, 0), f.created_at, f.updated_at, GETDATE()
      FROM stg.stg_files f
      LEFT JOIN (SELECT file_id, COUNT(*) AS version_count
                   FROM stg.stg_file_versions
                  GROUP BY file_id) v ON v.file_id = f.id
     WHERE f.created_at < DATEADD(day, 1, @business_date);
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_file', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
