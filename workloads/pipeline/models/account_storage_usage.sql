{{ config(database=database_for("doc_usage_dashboard"), period="snapshot_date", column_ddl="snapshot_date DATE, account_id VARCHAR(36), account_email VARCHAR(255), tier VARCHAR(16), quota_bytes NUMBER(19,0), used_bytes NUMBER(19,0), remaining_bytes NUMBER(19,0), usage_pct NUMBER(7,2), usage_band VARCHAR(16), active_document_count NUMBER(10,0)", columns_order=["snapshot_date", "account_id", "account_email", "tier", "quota_bytes", "used_bytes", "remaining_bytes", "usage_pct", "usage_band", "active_document_count"]) }}
with quotas as (
  {{ raw_rows("ADMIN_STORAGE_QUOTAS", "user_id", true) }}
), accounts as (
  {{ raw_rows("ADMIN_ADMIN_USERS", "id", true) }}
), documents as (
  {{ raw_rows("DOCUMENT_DOCUMENTS", "id", true) }}
)
select * from ({{ storage_usage("quotas", "accounts", "documents") }})
