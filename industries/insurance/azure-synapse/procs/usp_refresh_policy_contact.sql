-- Contact screen feed: display name plus the best label to show next to the phone.
CREATE PROCEDURE dw.usp_refresh_policy_contact
AS
BEGIN
    SET NOCOUNT ON;
    TRUNCATE TABLE dw.policy_contact;

    INSERT INTO dw.policy_contact (policy_number, holder_display_name, contact_label, primary_phone)
    SELECT policy_number,
           dw.fn_holder_display_name(holder_first, holder_middle, holder_last),
           ISNULL(NULLIF(alt_phone_label, ''), NULLIF(alt_phone, '')),
           primary_phone
      FROM dw.dim_policy;

    INSERT INTO dw.etl_log (proc_name, step, rows_affected)
    VALUES ('usp_refresh_policy_contact', 'insert', @@ROWCOUNT);
END
GO
