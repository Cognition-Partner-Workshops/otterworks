/*
  usp_load_dim_date
  Keeps the calendar populated from 2016-01-01 to the end of the business month.
  2016-03  dkessler   created
*/
CREATE OR ALTER PROCEDURE dbo.usp_load_dim_date
    @business_date date
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @run_id int, @d date, @end date, @rows int;
    SET @rows = 0;
    SET @d = '2016-01-01';
    SET @end = EOMONTH(@business_date);

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_date', @business_date = @business_date, @status = 'started', @run_id = @run_id OUTPUT;

    DELETE FROM dim.dim_date WHERE calendar_date BETWEEN @d AND @end;

    WHILE @d <= @end
    BEGIN
        INSERT INTO dim.dim_date
            (date_key, calendar_date, year_number, month_number, day_number, day_of_week,
             day_name, month_name, is_weekend, is_month_end, fiscal_quarter, loaded_at)
        VALUES
            (CONVERT(int, CONVERT(char(8), @d, 112)), @d, YEAR(@d), MONTH(@d), DAY(@d), DATEPART(weekday, @d),
             DATENAME(weekday, @d), DATENAME(month, @d),
             CASE WHEN DATENAME(weekday, @d) IN ('Saturday', 'Sunday') THEN 1 ELSE 0 END,
             CASE WHEN @d = EOMONTH(@d) THEN 1 ELSE 0 END,
             'FY' + RIGHT(CONVERT(varchar(4), YEAR(@d)), 2) + '-Q' + CONVERT(varchar(1), DATEPART(quarter, @d)),
             GETDATE());
        SET @rows = @rows + 1;
        SET @d = DATEADD(day, 1, @d);
    END

    EXEC dbo.usp_log_run @object_name = 'usp_load_dim_date', @business_date = @business_date, @status = 'succeeded', @rows_written = @rows, @run_id = @run_id;
END
GO
