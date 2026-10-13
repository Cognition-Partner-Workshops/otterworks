/*
  usp_load_dim_user
  Users from the auth extract, stamped with the tenant of their first workspace.
  2016-04  dkessler   created
  2018-05  tnguyen    email_domain from the package instead of parsing here
*/
CREATE OR ALTER PROCEDURE dbo.usp_load_dim_user
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_user', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM dim.dim_user;

    INSERT INTO dim.dim_user
        (user_id, tenant_id, email, email_domain, display_name, email_verified, mfa_enabled,
         created_at_utc, last_login_utc, loaded_at)
    SELECT u.id,
           (SELECT MIN(m.tenant_id) FROM stg.stg_auth_workspace_members m WHERE m.user_id = u.id),
           u.email,
           u.email_domain,
           u.display_name,
           u.email_verified,
           u.mfa_enabled,
           u.created_at,
           u.last_login_at,
           GETDATE()
      FROM stg.stg_auth_users u
     WHERE u.created_at < DATEADD(day, 1, @business_date);
    SET @rows = @@ROWCOUNT;

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_user', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
