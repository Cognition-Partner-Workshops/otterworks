-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout (etl/spark/jobs/py/common/schemas.py).
-- One SELECT per landing table, introduced by "-- landing: <area>/<TABLE>". Unmapped landing columns are NULL (no defensible live source).

-- landing: users/USER_ACTIVITY_DAILY
-- USER_ACTIVITY_ID=activity_id, ACTIVITY_DATE=activity_dt, LOGIN_COUNT=login_count.
-- ACTION_COUNT: NO live equivalent. Live has document_count, which SFX_USERS.P_ACTIVITY_DAILY loads as constant 0 and which
-- counts documents, not actions; mapping it would fabricate the ACTIONS output. Left NULL; the job row stays RED.
SELECT activity_id AS USER_ACTIVITY_ID, user_id AS USER_ID, activity_dt AS ACTIVITY_DATE, CAST(login_count AS BIGINT) AS LOGIN_COUNT,
       CAST(NULL AS BIGINT) AS ACTION_COUNT
FROM cpw.dbx_d1111_before.users__user_activity_daily;
