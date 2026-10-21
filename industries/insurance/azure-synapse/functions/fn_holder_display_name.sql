-- "Last, First Middle" for letters and the contact screen.
CREATE FUNCTION dw.fn_holder_display_name (
    @first  VARCHAR(40),
    @middle VARCHAR(40),
    @last   VARCHAR(40)
)
RETURNS VARCHAR(120)
AS
BEGIN
    RETURN RTRIM(CONCAT(@last, ', ', @first, ' ', NULLIF(@middle, '')));
END
GO
