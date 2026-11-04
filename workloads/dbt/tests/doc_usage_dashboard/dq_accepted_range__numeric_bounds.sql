{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_accepted_range']) }}
-- spec: quota_bytes > 0 (StorageQuota validation), used_bytes >= 0, remaining_bytes never below zero,
-- usage_pct >= 0, active_document_count >= 0 ("0 if none")
select snapshot_date, account_id, quota_bytes, used_bytes, remaining_bytes, usage_pct, active_document_count
from {{ ref('doc_usage_dashboard') }}
where quota_bytes <= 0 or used_bytes < 0 or remaining_bytes < 0 or usage_pct < 0 or active_document_count < 0
