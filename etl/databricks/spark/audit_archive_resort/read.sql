/* run=dbx-d1111 act=spark step=read consumer=audit_archive_resort */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT AUDIT_EVENT_ARCHIVE_ID, ACTOR_USER_ID, DOCUMENT_ID, EVENT_TYPE, EVENT_AT, DETAILS
FROM cpw.dbx_d1111_after.audit__spark_audit_archive_resort
ORDER BY EVENT_TYPE, EVENT_AT, AUDIT_EVENT_ARCHIVE_ID;
