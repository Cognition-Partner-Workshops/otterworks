CREATE VIEW IF NOT EXISTS {{ database }}.OPS.ACCOUNT_STORAGE_LOOKUP
COMMENT = {{ comment }} AS
SELECT snapshot_date, account_id, account_email, tier, quota_bytes, used_bytes,
  remaining_bytes, usage_pct, usage_band, active_document_count
FROM {{ database }}.APP.ACCOUNT_STORAGE_USAGE;

GRANT USAGE ON SCHEMA {{ database }}.OPS TO ROLE ROLE_CS_DOC_USAGE_DASHBOARD_SUPPORT_LOOKUP;
GRANT SELECT ON VIEW {{ database }}.OPS.ACCOUNT_STORAGE_LOOKUP TO ROLE ROLE_CS_DOC_USAGE_DASHBOARD_SUPPORT_LOOKUP;
