/*
  usp_log_run
  Writes the run log every package, procedure and job step uses.
  Call once with @run_id NULL to open a row (returns the new run_id), then
  again with that run_id to close it.
  2016-03  dkessler   created
  2017-11  mkowalski  rows_read for the SSIS packages
*/
CREATE OR ALTER PROCEDURE dbo.usp_log_run
    @object_name   nvarchar(128),
    @object_type   varchar(20)    = 'procedure',
    @business_date date           = NULL,
    @status        varchar(20),
    @rows_read     int            = NULL,
    @rows_written  int            = NULL,
    @message       nvarchar(4000) = NULL,
    @run_id        int            = NULL OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    IF @run_id IS NULL
    BEGIN
        INSERT INTO ops.etl_run_log
            (object_name, object_type, business_date, status, rows_read, rows_written,
             started_at, finished_at, host_name, message)
        VALUES
            (@object_name, @object_type, @business_date, @status, @rows_read, @rows_written,
             GETDATE(), NULL, HOST_NAME(), @message);

        SET @run_id = SCOPE_IDENTITY();
        RETURN;
    END

    UPDATE ops.etl_run_log
       SET status       = @status,
           rows_read    = ISNULL(@rows_read, rows_read),
           rows_written = ISNULL(@rows_written, rows_written),
           finished_at  = GETDATE(),
           message      = ISNULL(@message, message)
     WHERE run_id = @run_id;
END
GO
