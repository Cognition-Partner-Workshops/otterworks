-- run_token=dbx-d1111 expires=2026-11-24
-- Landing documents/COLLAB_SESSION (COLLAB_SESSION_ID, DOCUMENT_ID, USER_ID, SESSION_ID, EVENT_AT).
-- COLLAB_SESSION_ID <- session_id (UNIQUE PRIMARY INDEX, one row per event); EVENT_AT <- start_ts.
-- Every live row has start_ts = end_ts (checked in step=inputs), so each row is a point event.
-- Landing SESSION_ID (text token) has no live equivalent and is not read by the job: NULL.
SELECT session_id            AS COLLAB_SESSION_ID,
       document_id           AS DOCUMENT_ID,
       user_id               AS USER_ID,
       CAST(NULL AS STRING)  AS SESSION_ID,
       start_ts              AS EVENT_AT
FROM cpw.dbx_d1111_before.documents__collab_session
