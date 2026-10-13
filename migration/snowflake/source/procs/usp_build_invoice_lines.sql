/*
  usp_build_invoice_lines
  Invoice lines for every invoice issued so far in the business month, in cents.
  2016-07  dkessler   created
  2017-10  mkowalski  one invoice at a time so a bad header doesn't sink the batch
*/
CREATE OR ALTER PROCEDURE dbo.usp_build_invoice_lines
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @rows int, @rows_read int, @month_start date, @invoice_id varchar(36);
    SET @rows = 0;
    SET @rows_read = 0;
    SET @month_start = DATEADD(month, DATEDIFF(month, 0, @business_date), 0);

    EXEC dbo.usp_log_run @object_name = 'usp_build_invoice_lines', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM fact.fact_invoice_lines WHERE business_date = @business_date;

    DECLARE invoice_cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT DISTINCT invoice_id
          FROM stg.stg_billing_invoices
         WHERE issued_at >= @month_start
           AND issued_at < DATEADD(day, 1, @business_date);

    OPEN invoice_cur;
    FETCH NEXT FROM invoice_cur INTO @invoice_id;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @rows_read = @rows_read + 1;

        INSERT INTO fact.fact_invoice_lines
            (business_date, invoice_id, line_no, tenant_id, period_start, period_end, line_type,
             description, amount_cents, invoice_status, loaded_at)
        SELECT @business_date, i.invoice_id, i.line_no, i.tenant_id, i.period_start, i.period_end, i.line_type,
               i.description, CAST(i.amount * 100 AS int), i.status, GETDATE()
          FROM stg.stg_billing_invoices i
         WHERE i.invoice_id = @invoice_id;
        SET @rows = @rows + @@ROWCOUNT;

        FETCH NEXT FROM invoice_cur INTO @invoice_id;
    END
    CLOSE invoice_cur;
    DEALLOCATE invoice_cur;

    EXEC dbo.usp_log_run @object_name = 'usp_build_invoice_lines', @business_date = @business_date, @status = 'succeeded', @rows_read = @rows_read, @rows_written = @rows, @run_id = @run_id;
END
GO
