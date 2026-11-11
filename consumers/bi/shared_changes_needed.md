# Shared changes needed — bi-semantic

Status: **red**. The five billing queries passing their contracts do not cover
every successful read by `svc_bi_semantic`.

DBQL records 134 successful runs of
`SELECT TEAM_NAME, DISPLAY_NAME FROM SFX_USERS.V_TEAM_MEMBERS` and reads of
`SFX_USERS.TEAM`, `TEAM_MEMBER`, and `APP_USER`. The after schema is missing
`users__v_team_members`, `users__team`, and `users__team_member`.

In the shared round, build `cpw.dbx_d1111_after.users__v_team_members` and its
`users__team` / `users__team_member` dependencies (including the existing
`users__app_user` join), or retire the read with the BI owner. Preserve the
`TEAM_NAME`, `DISPLAY_NAME` output and prove input and result parity before
clearing the red status. This consumer fix does not create shared objects.

Blocking review:
https://github.com/Cognition-Partner-Workshops/otterworks/pull/2752#issuecomment-6787314604

Run `WAREHOUSE_CONTRACT_TARGET=databricks python -m pytest contract -v -s` to
check both billing parity and this dependency. The users test fails while any
required object is missing; it skips clearly for replay or absent credentials.
