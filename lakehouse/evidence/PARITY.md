# Lakehouse parity

| Spec | Coverage IDs | NS | Business date | Legacy rows | Lakehouse rows | Result |
|---|---|---|---|---:|---:|---|
| [billing.customer_account](parity/billing.customer_account.json) | teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT | sfx-d1110-after | 20261109 | 300 | 300 | PASS |
| [users.activity_latest](parity/users.activity_latest.json) | etl_script:etl/scripts/user_activity_daily.py | users-after | 20261109 | 1 | 1 | PASS |
| [users.activity_report](parity/users.activity_report.json) | etl_script:etl/scripts/user_activity_daily.py | users-after | 20261109 | 1 | 1 | PASS |
| [users.activity_user_summaries](parity/users.activity_user_summaries.json) | etl_script:etl/scripts/user_activity_daily.py | users-after | 20261109 | 4 | 4 | PASS |
| [users.app_user](parity/users.app_user.json) | teradata_table:SFX_USERS.APP_USER, bteq_script:warehouse/teradata/scripts/users/01_load_users.bteq | users-after | 20261109 | 300 | 300 | PASS |
| [users.infa_app_user](parity/users.infa_app_user.json) | informatica_mapping:SFX_CONTENT.m_SFX_APP_USER, informatica_session:SFX_CONTENT.s_m_SFX_APP_USER, informatica_source:SFX_CONTENT.STG_APP_USER, informatica_target:SFX_CONTENT.APP_USER | users-after | 20261109 | 300 | 300 | PASS |
| [users.infa_login_event](parity/users.infa_login_event.json) | informatica_mapping:SFX_CONTENT.m_SFX_LOGIN_EVENT, informatica_session:SFX_CONTENT.s_m_SFX_LOGIN_EVENT, informatica_source:SFX_CONTENT.FF_LOGIN_EVENT, informatica_target:SFX_CONTENT.LOGIN_EVENT | users-after | 20261109 | 2000 | 2000 | PASS |
| [users.infa_role_grant](parity/users.infa_role_grant.json) | informatica_mapping:SFX_CONTENT.m_SFX_ROLE_GRANT, informatica_session:SFX_CONTENT.s_m_SFX_ROLE_GRANT, informatica_source:SFX_CONTENT.FF_ROLE_GRANT, informatica_target:SFX_CONTENT.ROLE_GRANT | users-after | 20261109 | 200 | 200 | PASS |
| [users.infa_stg_app_user](parity/users.infa_stg_app_user.json) | informatica_mapping:SFX_CONTENT.m_SFX_STG_APP_USER, informatica_session:SFX_CONTENT.s_m_SFX_STG_APP_USER, informatica_source:SFX_CONTENT.FF_APP_USER, informatica_target:SFX_CONTENT.STG_APP_USER | users-after | 20261109 | 300 | 300 | PASS |
| [users.infa_team_member](parity/users.infa_team_member.json) | informatica_mapping:SFX_CONTENT.m_SFX_TEAM_MEMBER, informatica_session:SFX_CONTENT.s_m_SFX_TEAM_MEMBER, informatica_source:SFX_CONTENT.FF_TEAM_MEMBER, informatica_target:SFX_CONTENT.TEAM_MEMBER | users-after | 20261109 | 400 | 400 | PASS |
| [users.login_event](parity/users.login_event.json) | teradata_table:SFX_USERS.LOGIN_EVENT, bteq_script:warehouse/teradata/scripts/users/04_load_events.bteq | users-after | 20261109 | 2000 | 2000 | PASS |
| [users.role_grant](parity/users.role_grant.json) | teradata_table:SFX_USERS.ROLE_GRANT, bteq_script:warehouse/teradata/scripts/users/02_load_teams.bteq | users-after | 20261109 | 200 | 200 | PASS |
| [users.sso_identity](parity/users.sso_identity.json) | teradata_table:SFX_USERS.SSO_IDENTITY, bteq_script:warehouse/teradata/scripts/users/03_load_identity.bteq | users-after | 20261109 | 200 | 200 | PASS |
| [users.stg_app_user](parity/users.stg_app_user.json) | teradata_table:SFX_USERS.STG_APP_USER | users-after | 20261109 | 300 | 300 | PASS |
| [users.stg_login_event](parity/users.stg_login_event.json) | teradata_table:SFX_USERS.STG_LOGIN_EVENT | users-after | 20261109 | 2000 | 2000 | PASS |
| [users.stg_role_grant](parity/users.stg_role_grant.json) | teradata_table:SFX_USERS.STG_ROLE_GRANT | users-after | 20261109 | 200 | 200 | PASS |
| [users.stg_sso_identity](parity/users.stg_sso_identity.json) | teradata_table:SFX_USERS.STG_SSO_IDENTITY | users-after | 20261109 | 200 | 200 | PASS |
| [users.stg_team](parity/users.stg_team.json) | teradata_table:SFX_USERS.STG_TEAM | users-after | 20261109 | 20 | 20 | PASS |
| [users.stg_team_member](parity/users.stg_team_member.json) | teradata_table:SFX_USERS.STG_TEAM_MEMBER | users-after | 20261109 | 400 | 400 | PASS |
| [users.stg_user_activity_daily](parity/users.stg_user_activity_daily.json) | teradata_table:SFX_USERS.STG_USER_ACTIVITY_DAILY | users-after | 20261109 | 200 | 200 | PASS |
| [users.stg_user_pref](parity/users.stg_user_pref.json) | teradata_table:SFX_USERS.STG_USER_PREF | users-after | 20261109 | 200 | 200 | PASS |
| [users.stg_user_profile](parity/users.stg_user_profile.json) | teradata_table:SFX_USERS.STG_USER_PROFILE | users-after | 20261109 | 200 | 200 | PASS |
| [users.stg_user_status_hist](parity/users.stg_user_status_hist.json) | teradata_table:SFX_USERS.STG_USER_STATUS_HIST | users-after | 20261109 | 400 | 400 | PASS |
| [users.team](parity/users.team.json) | teradata_table:SFX_USERS.TEAM, bteq_script:warehouse/teradata/scripts/users/02_load_teams.bteq | users-after | 20261109 | 20 | 20 | PASS |
| [users.team_counts](parity/users.team_counts.json) | teradata_macro:SFX_USERS.M_TEAM_COUNTS, bteq_script:warehouse/teradata/scripts/users/10_activity_daily.bteq | users-after | 20261109 | 20 | 20 | PASS |
| [users.team_graph_components](parity/users.team_graph_components.json) | spark_job:team_graph_components | users-after | 20261109 | 70 | 70 | PASS |
| [users.team_member](parity/users.team_member.json) | teradata_table:SFX_USERS.TEAM_MEMBER, bteq_script:warehouse/teradata/scripts/users/02_load_teams.bteq | users-after | 20261109 | 400 | 400 | PASS |
| [users.user_activity_daily](parity/users.user_activity_daily.json) | teradata_table:SFX_USERS.USER_ACTIVITY_DAILY, bteq_script:warehouse/teradata/scripts/users/04_load_events.bteq, teradata_procedure:SFX_USERS.P_ACTIVITY_DAILY, bteq_script:warehouse/teradata/scripts/users/10_activity_daily.bteq | users-after | 20261109 | 400 | 400 | PASS |
| [users.user_pref](parity/users.user_pref.json) | teradata_table:SFX_USERS.USER_PREF | users-after | 20261109 | 0 | 0 | PASS |
| [users.user_pref_json_flatten](parity/users.user_pref_json_flatten.json) | spark_job:user_pref_json_flatten | users-after | 20261109 | 70 | 70 | PASS |
| [users.user_profile](parity/users.user_profile.json) | teradata_table:SFX_USERS.USER_PROFILE, bteq_script:warehouse/teradata/scripts/users/01_load_users.bteq | users-after | 20261109 | 200 | 200 | PASS |
| [users.user_status_hist](parity/users.user_status_hist.json) | teradata_table:SFX_USERS.USER_STATUS_HIST, bteq_script:warehouse/teradata/scripts/users/03_load_identity.bteq | users-after | 20261109 | 400 | 400 | PASS |
| [users.users_active_daily](parity/users.users_active_daily.json) | spark_job:users_active_daily | users-after | 20261109 | 7 | 7 | PASS |
| [users.users_login_useragent_parse](parity/users.users_login_useragent_parse.json) | spark_job:users_login_useragent_parse | users-after | 20261109 | 70 | 70 | PASS |
| [users.users_risk_score](parity/users.users_risk_score.json) | spark_job:users_risk_score | users-after | 20261109 | 70 | 70 | PASS |
| [users.users_risk_score_jdbc](parity/users.users_risk_score_jdbc.json) | spark_job:users_risk_score | users-after | 20261109 | 70 | 70 | PASS |
| [users.users_team_rollup](parity/users.users_team_rollup.json) | spark_job:users_team_rollup | users-after | 20261109 | 70 | 70 | PASS |
| [users.users_team_rollup_jdbc](parity/users.users_team_rollup_jdbc.json) | spark_job:users_team_rollup | users-after | 20261109 | 70 | 70 | PASS |
| [users.v_team_members](parity/users.v_team_members.json) | teradata_view:SFX_USERS.V_TEAM_MEMBERS | users-after | 20261109 | 400 | 400 | PASS |
| [users.v_user_settings](parity/users.v_user_settings.json) | teradata_view:SFX_USERS.V_USER_SETTINGS | users-after | 20261109 | 0 | 0 | PASS |
