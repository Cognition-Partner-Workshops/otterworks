-- First-pass conversion output: dw.fn_holder_display_name
CREATE OR REPLACE FUNCTION DW.FN_HOLDER_DISPLAY_NAME(P_FIRST VARCHAR, P_MIDDLE VARCHAR, P_LAST VARCHAR)
RETURNS VARCHAR
AS
$$
    -- FP-INFO 0401: CONCAT carried over unchanged
    RTRIM(CONCAT(P_LAST, ', ', P_FIRST, ' ', NULLIF(P_MIDDLE, '')))
$$;
