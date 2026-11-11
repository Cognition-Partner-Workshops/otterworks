/* run=dbx-d1111 act=spark step=transform consumer=lake_compaction_audit */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT * FROM AUDIT_DAILY_SUMMARY;
