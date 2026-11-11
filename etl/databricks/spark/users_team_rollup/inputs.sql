-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout (etl/spark/jobs/py/common/schemas.py).
-- One SELECT per landing table, introduced by "-- landing: <area>/<TABLE>". Unmapped landing columns are NULL (no defensible live source).

-- landing: users/TEAM
SELECT team_id AS TEAM_ID, owner_user_id AS OWNER_USER_ID, team_name AS TEAM_NAME
FROM cpw.dbx_d1111_before.users__team;

-- landing: users/TEAM_MEMBER
-- ROLE=rtrim(role_cd) (CHAR(12) pad, same as ../team_graph_components/inputs.sql). ROLE is not read by this job.
SELECT team_member_id AS TEAM_MEMBER_ID, team_id AS TEAM_ID, user_id AS USER_ID, rtrim(role_cd) AS ROLE
FROM cpw.dbx_d1111_before.users__team_member;

-- landing: users/APP_USER
-- STATUS=rtrim(status_cd) (CHAR(12) pad). CREATED_AT is TIMESTAMP in landing but live has DATE only: NULL. Neither is read by the job.
SELECT user_id AS USER_ID, email AS EMAIL, display_name AS DISPLAY_NAME, CAST(NULL AS TIMESTAMP) AS CREATED_AT, rtrim(status_cd) AS STATUS
FROM cpw.dbx_d1111_before.users__app_user;
