-- Customer email is visible only to sessions that have {{ analyst_role }} active
-- (primary or secondary). Everyone else, including the owning builder role, sees a mask.
CREATE MASKING POLICY IF NOT EXISTS {{ email_masking_policy }}
  AS (val VARCHAR) RETURNS VARCHAR ->
  CASE
    WHEN IS_ROLE_IN_SESSION('{{ analyst_role }}') THEN val
    WHEN val IS NULL THEN NULL
    ELSE '***MASKED***'
  END
  COMMENT = 'Customer email: clear for {{ analyst_role }}, masked for every other role';

ALTER TABLE {{ db_churn_model }}.RAW.AUTH_USERS
  MODIFY COLUMN EMAIL SET MASKING POLICY {{ email_masking_policy }};
ALTER TABLE {{ db_churn_model }}.RAW.ADMIN_ADMIN_USERS
  MODIFY COLUMN EMAIL SET MASKING POLICY {{ email_masking_policy }};
ALTER TABLE {{ db_doc_usage_dashboard }}.RAW.ADMIN_ADMIN_USERS
  MODIFY COLUMN EMAIL SET MASKING POLICY {{ email_masking_policy }};
