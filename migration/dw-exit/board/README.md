# Migration board

## Parity by subject area

An object counts as green only when its DuckDB column is green.
Snowflake login down; execution disabled.

| Subject area | DuckDB | Snowflake |
|---|---:|---:|
| **Total** | 29 green / 223 red | 0 green / 252 red |
| audit | 0 green / 57 red | 0 green / 57 red |
| billing | 29 green / 45 red | 0 green / 74 red |
| content | 0 green / 1 red | 0 green / 1 red |
| dbc | 0 green / 6 red | 0 green / 6 red |
| documents | 0 green / 59 red | 0 green / 59 red |
| users | 0 green / 55 red | 0 green / 55 red |

## Object parity

See [board.json](board.json) for reasons and measurement evidence.

| Object | Subject area | DuckDB | Snowflake |
|---|---|---|---|
| m_SFX_APP_USER | users | red | red |
| m_SFX_AUDIT_DAILY_SUMMARY | audit | red | red |
| m_SFX_AUDIT_EVENT | audit | red | red |
| m_SFX_AUDIT_EVENT_ARCHIVE | audit | red | red |
| m_SFX_CUSTOMER_ACCOUNT | billing | red | red |
| m_SFX_DOCUMENT | documents | red | red |
| m_SFX_DOC_SHARE | documents | red | red |
| m_SFX_GL_JOURNAL_LINE | billing | red | red |
| m_SFX_INVOICE_HDR | billing | red | red |
| m_SFX_INVOICE_LINE | billing | red | red |
| m_SFX_LOGIN_EVENT | users | red | red |
| m_SFX_PAYMENT | billing | red | red |
| m_SFX_ROLE_GRANT | users | red | red |
| m_SFX_SECURITY_ALERT | audit | red | red |
| m_SFX_STG_APP_USER | users | red | red |
| m_SFX_STG_AUDIT_EVENT | audit | red | red |
| m_SFX_STG_CUSTOMER_ACCOUNT | billing | green | red |
| m_SFX_STG_DOCUMENT | documents | red | red |
| m_SFX_STG_INVOICE_HDR | billing | green | red |
| m_SFX_TEAM_MEMBER | users | red | red |
| s_m_SFX_APP_USER | users | red | red |
| s_m_SFX_AUDIT_DAILY_SUMMARY | audit | red | red |
| s_m_SFX_AUDIT_EVENT | audit | red | red |
| s_m_SFX_AUDIT_EVENT_ARCHIVE | audit | red | red |
| s_m_SFX_CUSTOMER_ACCOUNT | billing | red | red |
| s_m_SFX_DOCUMENT | documents | red | red |
| s_m_SFX_DOC_SHARE | documents | red | red |
| s_m_SFX_GL_JOURNAL_LINE | billing | red | red |
| s_m_SFX_INVOICE_HDR | billing | red | red |
| s_m_SFX_INVOICE_LINE | billing | red | red |
| s_m_SFX_LOGIN_EVENT | users | red | red |
| s_m_SFX_PAYMENT | billing | red | red |
| s_m_SFX_ROLE_GRANT | users | red | red |
| s_m_SFX_SECURITY_ALERT | audit | red | red |
| s_m_SFX_STG_APP_USER | users | red | red |
| s_m_SFX_STG_AUDIT_EVENT | audit | red | red |
| s_m_SFX_STG_CUSTOMER_ACCOUNT | billing | green | red |
| s_m_SFX_STG_DOCUMENT | documents | red | red |
| s_m_SFX_STG_INVOICE_HDR | billing | green | red |
| s_m_SFX_TEAM_MEMBER | users | red | red |
| wf_SFX_AUDIT_DAILY | audit | red | red |
| wf_SFX_BILLING_DAILY | billing | red | red |
| wf_SFX_CONTENT_DAILY | content | red | red |
| wklt_SFX_BILLING_STAGE | billing | red | red |
| 01_load_accounts | billing | red | red |
| 01_load_events | audit | red | red |
| 01_load_folders | documents | red | red |
| 01_load_users | users | red | red |
| 02_current_versions | documents | red | red |
| 02_load_controls | audit | red | red |
| 02_load_subscriptions | billing | red | red |
| 02_load_teams | users | red | red |
| 03_load_access | documents | red | red |
| 03_load_identity | users | red | red |
| 03_load_invoices | billing | red | red |
| 03_load_reviews | audit | red | red |
| 04_load_events | users | red | red |
| 04_load_objects | documents | red | red |
| 04_load_payments | billing | red | red |
| 05_load_sessions | documents | red | red |
| 05_load_usage | billing | red | red |
| 10_activity_daily | users | red | red |
| 10_storage_monthly | documents | red | red |
| 10_subscription_report | billing | red | red |
| 10_summary_daily | audit | red | red |
| 11_currency_daily | billing | red | red |
| 11_reconciliation | audit | red | red |
| 12_invoice_monthly | billing | red | red |
| 13_period_close | billing | red | red |
| DBC.DBC_QRYLOG | dbc | red | red |
| DBC.DBC_QRYLOGOBJECTS | dbc | red | red |
| DBC.DBC_TABLESV | dbc | red | red |
| DBC.QRYLOGOBJECTSV | dbc | red | red |
| DBC.QRYLOGV | dbc | red | red |
| DBC.TABLESV | dbc | red | red |
| billing_billing_adj | billing | green | red |
| billing_credit_note | billing | green | red |
| billing_customer_account | billing | green | red |
| billing_gl_account | billing | green | red |
| billing_gl_journal_line | billing | green | red |
| billing_invoice_hdr | billing | green | red |
| billing_invoice_line | billing | green | red |
| billing_payment | billing | green | red |
| billing_plan_catalog | billing | green | red |
| billing_subscription | billing | green | red |
| billing_tax_rate | billing | green | red |
| billing_usage_daily | billing | green | red |
| users_app_user | users | red | red |
| users_login_event | users | red | red |
| users_role_grant | users | red | red |
| users_sso_identity | users | red | red |
| users_team | users | red | red |
| users_team_member | users | red | red |
| users_user_activity_daily | users | red | red |
| users_user_pref | users | red | red |
| users_user_profile | users | red | red |
| users_user_status_hist | users | red | red |
| SFX_AUDIT.M_ARCHIVE_OVERVIEW | audit | red | red |
| SFX_AUDIT.M_RECON_TOTALS | audit | red | red |
| SFX_BILLING.M_CURRENCY_TOTALS | billing | red | red |
| SFX_BILLING.M_SUBSCRIPTION_PLANS | billing | red | red |
| SFX_DOCUMENTS.M_STORAGE_TOTALS | documents | red | red |
| SFX_USERS.M_TEAM_COUNTS | users | red | red |
| SFX_AUDIT.P_DAILY_SUMMARY | audit | red | red |
| SFX_AUDIT.P_RECON_COUNTS | audit | red | red |
| SFX_BILLING.P_MONTHLY_INVOICE | billing | red | red |
| SFX_USERS.P_ACTIVITY_DAILY | users | red | red |
| SFX_AUDIT.ACCESS_REVIEW | audit | red | red |
| SFX_AUDIT.AUDIT_DAILY_SUMMARY | audit | red | red |
| SFX_AUDIT.AUDIT_EVENT | audit | red | red |
| SFX_AUDIT.AUDIT_EVENT_ARCHIVE | audit | red | red |
| SFX_AUDIT.AUDIT_RECON | audit | red | red |
| SFX_AUDIT.COMPLIANCE_FLAG | audit | red | red |
| SFX_AUDIT.DATA_EXPORT_REQ | audit | red | red |
| SFX_AUDIT.LEGAL_HOLD | audit | red | red |
| SFX_AUDIT.RETENTION_POLICY | audit | red | red |
| SFX_AUDIT.SECURITY_ALERT | audit | red | red |
| SFX_AUDIT.STG_ACCESS_REVIEW | audit | red | red |
| SFX_AUDIT.STG_AUDIT_DAILY_SUMMARY | audit | red | red |
| SFX_AUDIT.STG_AUDIT_EVENT | audit | red | red |
| SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE | audit | red | red |
| SFX_AUDIT.STG_AUDIT_RECON | audit | red | red |
| SFX_AUDIT.STG_COMPLIANCE_FLAG | audit | red | red |
| SFX_AUDIT.STG_DATA_EXPORT_REQ | audit | red | red |
| SFX_AUDIT.STG_LEGAL_HOLD | audit | red | red |
| SFX_AUDIT.STG_RETENTION_POLICY | audit | red | red |
| SFX_AUDIT.STG_SECURITY_ALERT | audit | red | red |
| SFX_BILLING.BILLING_ADJ | billing | red | red |
| SFX_BILLING.CREDIT_NOTE | billing | red | red |
| SFX_BILLING.CUSTOMER_ACCOUNT | billing | red | red |
| SFX_BILLING.GL_ACCOUNT | billing | red | red |
| SFX_BILLING.GL_JOURNAL_LINE | billing | red | red |
| SFX_BILLING.INVOICE_HDR | billing | red | red |
| SFX_BILLING.INVOICE_LINE | billing | red | red |
| SFX_BILLING.PAYMENT | billing | red | red |
| SFX_BILLING.PLAN_CATALOG | billing | red | red |
| SFX_BILLING.STG_BILLING_ADJ | billing | green | red |
| SFX_BILLING.STG_CREDIT_NOTE | billing | green | red |
| SFX_BILLING.STG_CUSTOMER_ACCOUNT | billing | green | red |
| SFX_BILLING.STG_GL_ACCOUNT | billing | green | red |
| SFX_BILLING.STG_GL_JOURNAL_LINE | billing | green | red |
| SFX_BILLING.STG_INVOICE_HDR | billing | green | red |
| SFX_BILLING.STG_INVOICE_LINE | billing | green | red |
| SFX_BILLING.STG_PAYMENT | billing | green | red |
| SFX_BILLING.STG_PLAN_CATALOG | billing | green | red |
| SFX_BILLING.STG_SUBSCRIPTION | billing | green | red |
| SFX_BILLING.STG_TAX_RATE | billing | green | red |
| SFX_BILLING.STG_USAGE_DAILY | billing | green | red |
| SFX_BILLING.SUBSCRIPTION | billing | red | red |
| SFX_BILLING.TAX_RATE | billing | green | red |
| SFX_BILLING.USAGE_DAILY | billing | red | red |
| SFX_DOCUMENTS.COLLAB_SESSION | documents | red | red |
| SFX_DOCUMENTS.DOCUMENT | documents | red | red |
| SFX_DOCUMENTS.DOC_COMMENT | documents | red | red |
| SFX_DOCUMENTS.DOC_SHARE | documents | red | red |
| SFX_DOCUMENTS.DOC_TAG | documents | red | red |
| SFX_DOCUMENTS.DOC_VERSION | documents | red | red |
| SFX_DOCUMENTS.FILE_OBJECT | documents | red | red |
| SFX_DOCUMENTS.FOLDER | documents | red | red |
| SFX_DOCUMENTS.SEARCH_INDEX_LOG | documents | red | red |
| SFX_DOCUMENTS.STG_COLLAB_SESSION | documents | red | red |
| SFX_DOCUMENTS.STG_DOCUMENT | documents | red | red |
| SFX_DOCUMENTS.STG_DOC_COMMENT | documents | red | red |
| SFX_DOCUMENTS.STG_DOC_SHARE | documents | red | red |
| SFX_DOCUMENTS.STG_DOC_TAG | documents | red | red |
| SFX_DOCUMENTS.STG_DOC_VERSION | documents | red | red |
| SFX_DOCUMENTS.STG_FILE_OBJECT | documents | red | red |
| SFX_DOCUMENTS.STG_FOLDER | documents | red | red |
| SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG | documents | red | red |
| SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY | documents | red | red |
| SFX_DOCUMENTS.STORAGE_USAGE_DAILY | documents | red | red |
| SFX_USERS.APP_USER | users | red | red |
| SFX_USERS.LOGIN_EVENT | users | red | red |
| SFX_USERS.ROLE_GRANT | users | red | red |
| SFX_USERS.SSO_IDENTITY | users | red | red |
| SFX_USERS.STG_APP_USER | users | red | red |
| SFX_USERS.STG_LOGIN_EVENT | users | red | red |
| SFX_USERS.STG_ROLE_GRANT | users | red | red |
| SFX_USERS.STG_SSO_IDENTITY | users | red | red |
| SFX_USERS.STG_TEAM | users | red | red |
| SFX_USERS.STG_TEAM_MEMBER | users | red | red |
| SFX_USERS.STG_USER_ACTIVITY_DAILY | users | red | red |
| SFX_USERS.STG_USER_PREF | users | red | red |
| SFX_USERS.STG_USER_PROFILE | users | red | red |
| SFX_USERS.STG_USER_STATUS_HIST | users | red | red |
| SFX_USERS.TEAM | users | red | red |
| SFX_USERS.TEAM_MEMBER | users | red | red |
| SFX_USERS.USER_ACTIVITY_DAILY | users | red | red |
| SFX_USERS.USER_PREF | users | red | red |
| SFX_USERS.USER_PROFILE | users | red | red |
| SFX_USERS.USER_STATUS_HIST | users | red | red |
| audit_access_review | audit | red | red |
| audit_audit_daily_summary | audit | red | red |
| audit_audit_event | audit | red | red |
| audit_audit_event_archive | audit | red | red |
| audit_audit_recon | audit | red | red |
| audit_compliance_flag | audit | red | red |
| audit_data_export_req | audit | red | red |
| audit_legal_hold | audit | red | red |
| audit_retention_policy | audit | red | red |
| audit_security_alert | audit | red | red |
| documents_collab_session | documents | red | red |
| documents_doc_comment | documents | red | red |
| documents_doc_share | documents | red | red |
| documents_doc_tag | documents | red | red |
| documents_doc_version | documents | red | red |
| documents_document | documents | red | red |
| documents_file_object | documents | red | red |
| documents_folder | documents | red | red |
| documents_search_index_log | documents | red | red |
| documents_storage_usage_daily | documents | red | red |
| SFX_AUDIT.V_CUSTOMER_RECON | audit | red | red |
| SFX_AUDIT.V_EVENT_ACTORS | audit | red | red |
| SFX_BILLING.V_ACCOUNT_INVOICES | billing | red | red |
| SFX_BILLING.V_INVOICE_BASE | billing | red | red |
| SFX_BILLING.V_INVOICE_REVENUE | billing | red | red |
| SFX_BILLING.V_SUBSCRIPTION_PLANS | billing | red | red |
| SFX_DOCUMENTS.V_DOCUMENT_VERSIONS | documents | red | red |
| SFX_DOCUMENTS.V_SEARCH_HISTORY | documents | red | red |
| SFX_DOCUMENTS.V_WORKSPACE_STORAGE | documents | red | red |
| SFX_USERS.V_TEAM_MEMBERS | users | red | red |
| SFX_USERS.V_USER_SETTINGS | users | red | red |
| audit_actor_activity_join | audit | red | red |
| audit_archive_resort | audit | red | red |
| audit_daily_summary | audit | red | red |
| billing_churn_score | billing | red | red |
| billing_gl_trial_balance | billing | red | red |
| billing_invoice_summary_daily | billing | red | red |
| billing_payment_aging | billing | red | red |
| billing_revenue_by_plan | billing | red | red |
| billing_usage_append_daily | billing | red | red |
| collab_session_sessionize | documents | red | red |
| compliance_flag_rules | audit | red | red |
| doc_share_graph_reach | documents | red | red |
| doc_version_diff_stats | documents | red | red |
| docs_event_export_hourly | documents | red | red |
| docs_folder_legacy_report | documents | red | red |
| docs_folder_tree_walk | documents | red | red |
| docs_search_log_parse | documents | red | red |
| docs_share_activity | documents | red | red |
| docs_storage_by_owner | documents | red | red |
| docs_tag_normalize | documents | red | red |
| file_object_binary_extract | documents | red | red |
| lake_compaction_audit | audit | red | red |
| lake_compaction_documents | documents | red | red |
| security_alert_anomaly | documents | red | red |
| team_graph_components | users | red | red |
| user_pref_json_flatten | users | red | red |
| users_active_daily | users | red | red |
| users_login_useragent_parse | users | red | red |
| users_risk_score | users | red | red |
| users_team_rollup | users | red | red |

## Waves

| Count | Wave 1 | Wave 2 | Wave 3 | Wave 4 |
|---|---:|---:|---:|---:|
| Total | 108 | 51 | 82 | 11 |
| by_kind: bteq | 0 | 12 | 13 | 0 |
| by_kind: catalog | 6 | 0 | 0 | 0 |
| by_kind: fastload | 22 | 0 | 0 | 0 |
| by_kind: macro | 1 | 0 | 5 | 0 |
| by_kind: mapping | 6 | 9 | 5 | 0 |
| by_kind: procedure | 0 | 0 | 4 | 0 |
| by_kind: session | 6 | 9 | 5 | 0 |
| by_kind: spark_job | 0 | 0 | 30 | 0 |
| by_kind: table | 45 | 21 | 18 | 0 |
| by_kind: tpt | 20 | 0 | 0 | 0 |
| by_kind: view | 2 | 0 | 0 | 9 |
| by_kind: workflow | 0 | 0 | 1 | 2 |
| by_kind: worklet | 0 | 0 | 1 | 0 |
| by_target: compatibility_view | 0 | 0 | 0 | 9 |
| by_target: dbt_model | 49 | 35 | 55 | 0 |
| by_target: retire | 20 | 0 | 0 | 0 |
| by_target: snowflake_scripting | 39 | 12 | 24 | 2 |
| by_target: snowpark | 0 | 4 | 3 | 0 |

## Licence counters

| Counter | Remaining | Target |
|---|---:|---:|
| teradata_objects | 178 | 0 |
| powercenter_mappings | 20 | 0 |
| powercenter_objects | 44 | 0 |
| spark_jobs | 30 | 0 |
| licence_dependencies | 252 | 0 |

All objects remain not_started. Parity measurements do not migrate or retire objects.
