-- First-pass conversion output: dw.usp_refresh_policy_contact
CREATE OR REPLACE PROCEDURE DW.USP_REFRESH_POLICY_CONTACT()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    TRUNCATE TABLE DW.POLICY_CONTACT;
    INSERT INTO DW.POLICY_CONTACT (policy_number, holder_display_name, contact_label, primary_phone)
    SELECT policy_number,
           DW.FN_HOLDER_DISPLAY_NAME(holder_first, holder_middle, holder_last),
           -- FP-INFO 0415: ISNULL mapped to COALESCE
           COALESCE(NULLIF(alt_phone_label, ''), NULLIF(alt_phone, '')),
           primary_phone
      FROM DW.DIM_POLICY;
    INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected) VALUES ('usp_refresh_policy_contact', 'insert', :SQLROWCOUNT);
    RETURN 'ok';
END;
$$;
