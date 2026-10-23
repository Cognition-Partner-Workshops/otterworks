/*
  usp_load_dim_workspace
  Workspaces as seen through the auth membership extract.
  2016-04  dkessler   created
*/
CREATE OR ALTER PROCEDURE dbo.usp_load_dim_workspace
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_workspace', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM dim.dim_workspace;

    INSERT INTO dim.dim_workspace (workspace_id, workspace_name, tenant_id, member_count, loaded_at)
    SELECT m.workspace_id, MAX(m.workspace_name), MAX(m.tenant_id), COUNT(*), GETDATE()
      FROM stg.stg_auth_workspace_members m
     WHERE m.joined_at < DATEADD(day, 1, @business_date)
     GROUP BY m.workspace_id;
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_workspace', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
