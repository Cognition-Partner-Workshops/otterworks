-- run_token=dbx-d1111 expires=2026-11-24
-- Landing users/TEAM_MEMBER (TEAM_MEMBER_ID, TEAM_ID, USER_ID, ROLE) from the live baseline.
-- ROLE <- role_cd (CHAR(12) in warehouse/teradata/ddl/users/00_tables.sql, trailing pad trimmed). joined_dt has no landing column.
SELECT team_member_id AS TEAM_MEMBER_ID,
       team_id        AS TEAM_ID,
       user_id        AS USER_ID,
       rtrim(role_cd) AS ROLE
FROM cpw.dbx_d1111_before.users__team_member
