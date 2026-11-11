/* run=dbx-d1111 act=spark step=inputs consumer=audit_archive_resort */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT archive_id AS AUDIT_EVENT_ARCHIVE_ID, actor_user_id AS ACTOR_USER_ID,
 document_id AS DOCUMENT_ID, event_type AS EVENT_TYPE, event_ts AS EVENT_AT, details AS DETAILS
FROM cpw.dbx_d1111_before.audit__stg_audit_event_archive;
-- Recheck: final archive is empty; its independent live staging table has 200 rows.
-- Same documented archive columns, no synthetic values or transformations.
