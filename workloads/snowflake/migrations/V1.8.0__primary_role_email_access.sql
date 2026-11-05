-- Secondary analyst roles must not unmask email; READER reads workload outputs only.
ALTER MASKING POLICY {{ email_masking_policy }} SET BODY ->
  CASE
    WHEN CURRENT_ROLE() = '{{ analyst_role }}' THEN val
    WHEN val IS NULL THEN NULL
    ELSE '***MASKED***'
  END;
ALTER MASKING POLICY {{ email_masking_policy }}
  SET COMMENT = 'Customer email: clear only when the primary role is {{ analyst_role }}; secondary roles never unmask';

REVOKE SELECT ON TABLE {{ db_churn_model }}.RAW.AUTH_USERS FROM ROLE {{ reader_role }};
REVOKE USAGE ON SCHEMA {{ db_churn_model }}.RAW FROM ROLE {{ reader_role }};
