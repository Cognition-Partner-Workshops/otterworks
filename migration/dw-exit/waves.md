# Wave plan

Generated from manifest rules and dependency edges. All objects remain not_started.
Counts are planned scope, not completed migrations or realized licence savings.

DBQL window: 2026-08-12..2026-11-09. Spark window: newest packaged start date minus 89 days through that date.
Containment/data-availability edges do not prescribe execution order within a wave.

## Wave 1

Objects: 111

Entry: Approve retirement evidence and rollback/retention policy; provision Snowflake landing, roles and observability.

Exit: Owner signs retirement; retention and restore tested; replacement feeds pass counts/schema checks.

Earlier-wave dependencies must pass their exit criteria; same-wave dependencies must be available before each dependent cuts over.

### Scope counts

| Dimension | Value | Count |
|---|---|---:|
| system | powercenter | 12 |
| system | spark | 3 |
| system | teradata | 96 |
| kind | catalog | 6 |
| kind | fastload | 22 |
| kind | macro | 1 |
| kind | mapping | 6 |
| kind | session | 6 |
| kind | spark_job | 3 |
| kind | table | 45 |
| kind | tpt | 20 |
| kind | view | 2 |
| target_type | dbt_model | 49 |
| target_type | retire | 23 |
| target_type | snowflake_scripting | 39 |

Licence dependencies eligible to free after verified cutover/decommission: powercenter: 12 objects, spark: 3 objects, teradata: 96 objects.
Teradata compute/catalog access, PowerCenter execution and Spark scheduling/compute can be removed only after all dependent consumers and retention obligations are cleared. These are object counts, not additive monetary savings.

### audit

- **SFX_AUDIT.AUDIT_EVENT_ARCHIVE** — @otterworks/data-platform; teradata/table; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_AUDIT.M_ARCHIVE_OVERVIEW** — @otterworks/data-platform; teradata/macro; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_AUDIT.STG_ACCESS_REVIEW** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__access_review`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_access_review (wave 1)
- **SFX_AUDIT.STG_AUDIT_DAILY_SUMMARY** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__audit_daily_summary`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_audit_daily_summary (wave 1)
- **SFX_AUDIT.STG_AUDIT_EVENT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__audit_event`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_audit_event (wave 1), m_SFX_STG_AUDIT_EVENT (wave 1)
- **SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE** — @otterworks/finance-reporting; teradata/table; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_AUDIT.STG_AUDIT_RECON** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__audit_recon`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_audit_recon (wave 1)
- **SFX_AUDIT.STG_COMPLIANCE_FLAG** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__compliance_flag`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_compliance_flag (wave 1)
- **SFX_AUDIT.STG_DATA_EXPORT_REQ** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__data_export_req`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_data_export_req (wave 1)
- **SFX_AUDIT.STG_LEGAL_HOLD** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__legal_hold`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_legal_hold (wave 1)
- **SFX_AUDIT.STG_RETENTION_POLICY** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__retention_policy`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_retention_policy (wave 1)
- **SFX_AUDIT.STG_SECURITY_ALERT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_audit__security_alert`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: audit_security_alert (wave 1)
- **audit_access_review** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_audit_daily_summary** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_audit_event** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_audit_event_archive** — @otterworks/finance-reporting; teradata/tpt; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **audit_audit_recon** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_compliance_flag** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_data_export_req** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_legal_hold** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_retention_policy** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **audit_security_alert** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_AUDIT.LOAD_AUDIT`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **lake_compaction_audit** — @otterworks/data-platform; spark/spark_job; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_AUDIT_EVENT_ARCHIVE** — @otterworks/data-platform; powercenter/mapping; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_STG_AUDIT_EVENT** — @otterworks/data-platform; powercenter/mapping; dbt_model → `stg_audit__m_sfx_stg_audit_event`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_AUDIT_EVENT_ARCHIVE** — @otterworks/data-platform; powercenter/session; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_STG_AUDIT_EVENT** — @otterworks/data-platform; powercenter/session; dbt_model → `stg_audit__s_m_sfx_stg_audit_event`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: m_SFX_STG_AUDIT_EVENT (wave 1)
### billing

- **SFX_BILLING.STG_BILLING_ADJ** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__billing_adj`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_billing_adj (wave 1)
- **SFX_BILLING.STG_CREDIT_NOTE** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__credit_note`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_credit_note (wave 1)
- **SFX_BILLING.STG_CUSTOMER_ACCOUNT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__customer_account`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_customer_account (wave 1), m_SFX_STG_CUSTOMER_ACCOUNT (wave 1)
- **SFX_BILLING.STG_GL_ACCOUNT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__gl_account`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_gl_account (wave 1)
- **SFX_BILLING.STG_GL_JOURNAL_LINE** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__gl_journal_line`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_gl_journal_line (wave 1)
- **SFX_BILLING.STG_INVOICE_HDR** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__invoice_hdr`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_invoice_hdr (wave 1), m_SFX_STG_INVOICE_HDR (wave 1)
- **SFX_BILLING.STG_INVOICE_LINE** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__invoice_line`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_invoice_line (wave 1)
- **SFX_BILLING.STG_PAYMENT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__payment`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_payment (wave 1)
- **SFX_BILLING.STG_PLAN_CATALOG** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__plan_catalog`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_plan_catalog (wave 1)
- **SFX_BILLING.STG_SUBSCRIPTION** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__subscription`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_subscription (wave 1)
- **SFX_BILLING.STG_TAX_RATE** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__tax_rate`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_tax_rate (wave 1)
- **SFX_BILLING.STG_USAGE_DAILY** — @otterworks/data-platform; teradata/table; dbt_model → `stg_billing__usage_daily`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: billing_usage_daily (wave 1)
- **billing_billing_adj** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_credit_note** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_customer_account** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_gl_account** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_gl_journal_line** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_invoice_hdr** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_invoice_line** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_payment** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_plan_catalog** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_subscription** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_tax_rate** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **billing_usage_daily** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_BILLING.LOAD_BILLING`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_STG_CUSTOMER_ACCOUNT** — @otterworks/data-platform; powercenter/mapping; dbt_model → `stg_billing__m_sfx_stg_customer_account`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_STG_INVOICE_HDR** — @otterworks/data-platform; powercenter/mapping; dbt_model → `stg_billing__m_sfx_stg_invoice_hdr`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_STG_CUSTOMER_ACCOUNT** — @otterworks/data-platform; powercenter/session; dbt_model → `stg_billing__s_m_sfx_stg_customer_account`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: m_SFX_STG_CUSTOMER_ACCOUNT (wave 1)
- **s_m_SFX_STG_INVOICE_HDR** — @otterworks/data-platform; powercenter/session; dbt_model → `stg_billing__s_m_sfx_stg_invoice_hdr`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: m_SFX_STG_INVOICE_HDR (wave 1)
### dbc

- **DBC.DBC_QRYLOG** — @otterworks/finance-reporting; teradata/catalog; retire → `SNOWFLAKE.ACCOUNT_USAGE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **DBC.DBC_QRYLOGOBJECTS** — @otterworks/finance-reporting; teradata/catalog; retire → `SNOWFLAKE.ACCOUNT_USAGE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **DBC.DBC_TABLESV** — @otterworks/finance-reporting; teradata/catalog; retire → `SNOWFLAKE.ACCOUNT_USAGE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **DBC.QRYLOGOBJECTSV** — @otterworks/finance-reporting; teradata/catalog; retire → `SNOWFLAKE.ACCOUNT_USAGE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **DBC.QRYLOGV** — @otterworks/finance-reporting; teradata/catalog; retire → `SNOWFLAKE.ACCOUNT_USAGE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **DBC.TABLESV** — @otterworks/finance-reporting; teradata/catalog; retire → `SNOWFLAKE.ACCOUNT_USAGE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
### documents

- **SFX_DOCUMENTS.SEARCH_INDEX_LOG** — @otterworks/data-platform; teradata/table; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_DOCUMENTS.STG_COLLAB_SESSION** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__collab_session`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_collab_session (wave 1)
- **SFX_DOCUMENTS.STG_DOCUMENT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__document`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_document (wave 1), m_SFX_STG_DOCUMENT (wave 1)
- **SFX_DOCUMENTS.STG_DOC_COMMENT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__doc_comment`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_doc_comment (wave 1)
- **SFX_DOCUMENTS.STG_DOC_SHARE** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__doc_share`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_doc_share (wave 1)
- **SFX_DOCUMENTS.STG_DOC_TAG** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__doc_tag`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_doc_tag (wave 1)
- **SFX_DOCUMENTS.STG_DOC_VERSION** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__doc_version`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_doc_version (wave 1)
- **SFX_DOCUMENTS.STG_FILE_OBJECT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__file_object`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_file_object (wave 1)
- **SFX_DOCUMENTS.STG_FOLDER** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__folder`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_folder (wave 1)
- **SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG** — @otterworks/finance-reporting; teradata/table; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY** — @otterworks/data-platform; teradata/table; dbt_model → `stg_documents__storage_usage_daily`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: documents_storage_usage_daily (wave 1)
- **SFX_DOCUMENTS.V_SEARCH_HISTORY** — @otterworks/data-platform; teradata/view; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **docs_folder_legacy_report** — @otterworks/data-platform; spark/spark_job; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **documents_collab_session** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_doc_comment** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_doc_share** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_doc_tag** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_doc_version** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_document** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_file_object** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_folder** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **documents_search_index_log** — @otterworks/finance-reporting; teradata/tpt; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **documents_storage_usage_daily** — @otterworks/data-platform; teradata/tpt; snowflake_scripting → `RAW_DOCUMENTS.LOAD_DOCUMENTS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **lake_compaction_documents** — @otterworks/data-platform; spark/spark_job; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_STG_DOCUMENT** — @otterworks/data-platform; powercenter/mapping; dbt_model → `stg_documents__m_sfx_stg_document`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_STG_DOCUMENT** — @otterworks/data-platform; powercenter/session; dbt_model → `stg_documents__s_m_sfx_stg_document`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: m_SFX_STG_DOCUMENT (wave 1)
### users

- **SFX_USERS.STG_APP_USER** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__app_user`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: m_SFX_STG_APP_USER (wave 1), users_app_user (wave 1)
- **SFX_USERS.STG_LOGIN_EVENT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__login_event`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_login_event (wave 1)
- **SFX_USERS.STG_ROLE_GRANT** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__role_grant`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_role_grant (wave 1)
- **SFX_USERS.STG_SSO_IDENTITY** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__sso_identity`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_sso_identity (wave 1)
- **SFX_USERS.STG_TEAM** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__team`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_team (wave 1)
- **SFX_USERS.STG_TEAM_MEMBER** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__team_member`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_team_member (wave 1)
- **SFX_USERS.STG_USER_ACTIVITY_DAILY** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__user_activity_daily`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_user_activity_daily (wave 1)
- **SFX_USERS.STG_USER_PREF** — @otterworks/data-platform; teradata/table; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_USERS.STG_USER_PROFILE** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__user_profile`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_user_profile (wave 1)
- **SFX_USERS.STG_USER_STATUS_HIST** — @otterworks/data-platform; teradata/table; dbt_model → `stg_users__user_status_hist`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: users_user_status_hist (wave 1)
- **SFX_USERS.USER_PREF** — @otterworks/data-platform; teradata/table; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_USERS.V_USER_SETTINGS** — @otterworks/data-platform; teradata/view; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_STG_APP_USER** — @otterworks/data-platform; powercenter/mapping; dbt_model → `stg_users__m_sfx_stg_app_user`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_STG_APP_USER** — @otterworks/data-platform; powercenter/session; dbt_model → `stg_users__s_m_sfx_stg_app_user`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: m_SFX_STG_APP_USER (wave 1)
- **users_app_user** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_login_event** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_role_grant** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_sso_identity** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_team** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_team_member** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_user_activity_daily** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_user_pref** — @otterworks/data-platform; teradata/fastload; retire → `NONE`.
  - Placement: retirement / storage or catalog replacement; final wave = max(floor, upstream waves). Dependencies: none
- **users_user_profile** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none
- **users_user_status_hist** — @otterworks/data-platform; teradata/fastload; snowflake_scripting → `RAW_USERS.LOAD_USERS`.
  - Placement: landing/load/staging foundation: wave 1; final wave = max(floor, upstream waves). Dependencies: none

### Retirement list and evidence

- **DBC.DBC_QRYLOG** — replaced by SNOWFLAKE.ACCOUNT_USAGE
  - reads=2; writes=0; last read=2026-08-12 06:04:02; last write=None; last QueryID/principal=111000000066 / svc_report_recon; feeds dead=n/a
- **DBC.DBC_QRYLOGOBJECTS** — replaced by SNOWFLAKE.ACCOUNT_USAGE
  - reads=2; writes=0; last read=2026-08-12 06:03:31; last write=None; last QueryID/principal=111000000065 / svc_report_recon; feeds dead=n/a
- **DBC.DBC_TABLESV** — replaced by SNOWFLAKE.ACCOUNT_USAGE
  - reads=2; writes=0; last read=2026-08-12 06:05:30; last write=None; last QueryID/principal=111000000067 / svc_report_recon; feeds dead=n/a
- **DBC.QRYLOGOBJECTSV** — replaced by SNOWFLAKE.ACCOUNT_USAGE
  - reads=1; writes=0; last read=2026-08-12 06:03:31; last write=None; last QueryID/principal=111000000065 / svc_report_recon; feeds dead=n/a
- **DBC.QRYLOGV** — replaced by SNOWFLAKE.ACCOUNT_USAGE
  - reads=1; writes=0; last read=2026-08-12 06:04:02; last write=None; last QueryID/principal=111000000066 / svc_report_recon; feeds dead=n/a
- **DBC.TABLESV** — replaced by SNOWFLAKE.ACCOUNT_USAGE
  - reads=1; writes=0; last read=2026-08-12 06:05:30; last write=None; last QueryID/principal=111000000067 / svc_report_recon; feeds dead=n/a
- **SFX_AUDIT.AUDIT_EVENT_ARCHIVE** — no DBQL usage in 90-day window
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=n/a
- **SFX_AUDIT.M_ARCHIVE_OVERVIEW** — no DBQL usage in 90-day window
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=n/a
- **SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE** — feeds only dead objects
  - reads=1; writes=0; last read=2026-08-12 06:06:11; last write=None; last QueryID/principal=111000000068 / svc_report_recon; feeds dead=SFX_AUDIT.AUDIT_EVENT_ARCHIVE
- **SFX_DOCUMENTS.SEARCH_INDEX_LOG** — no DBQL usage in 90-day window
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=n/a
- **SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG** — feeds only dead objects
  - reads=1; writes=0; last read=2026-08-12 06:09:53; last write=None; last QueryID/principal=111000000071 / svc_report_recon; feeds dead=SFX_DOCUMENTS.SEARCH_INDEX_LOG
- **SFX_DOCUMENTS.V_SEARCH_HISTORY** — no DBQL usage in 90-day window
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=n/a
- **SFX_USERS.STG_USER_PREF** — feeds only dead objects
  - reads=0; writes=20; last read=None; last write=2026-11-07 00:18:06; last QueryID/principal=111000007628 / svc_fastload; feeds dead=SFX_USERS.USER_PREF
- **SFX_USERS.USER_PREF** — no DBQL usage in 90-day window
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=n/a
- **SFX_USERS.V_USER_SETTINGS** — no DBQL usage in 90-day window
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=n/a
- **audit_audit_event_archive** — feeds only dead objects
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=SFX_AUDIT.AUDIT_EVENT_ARCHIVE
- **docs_folder_legacy_report** — disabled cron or no runs in window, and no output readers
  - runs=0; last run=2026-07-15T20:25:29.129Z; cron={"schedule": "11 2 * * *", "state": "disabled"}; readers=[]
- **documents_search_index_log** — feeds only dead objects
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=SFX_DOCUMENTS.SEARCH_INDEX_LOG
- **lake_compaction_audit** — replaced by Snowflake storage management
  - runs=1; last run=2026-11-10T20:27:35.087Z; cron={"schedule": "20 3 * * *", "state": "enabled"}; readers=[]
- **lake_compaction_documents** — replaced by Snowflake storage management
  - runs=1; last run=2026-11-10T20:27:08.884Z; cron={"schedule": "19 2 * * *", "state": "enabled"}; readers=[]
- **m_SFX_AUDIT_EVENT_ARCHIVE** — high complexity; feeds only dead objects
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=SFX_AUDIT.AUDIT_EVENT_ARCHIVE
- **s_m_SFX_AUDIT_EVENT_ARCHIVE** — feeds only dead objects
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=SFX_AUDIT.AUDIT_EVENT_ARCHIVE
- **users_user_pref** — feeds only dead objects
  - reads=0; writes=0; last read=None; last write=None; last QueryID/principal=None / None; feeds dead=SFX_USERS.USER_PREF

## Wave 2

Objects: 72

Entry: Foundation feeds and staging reconciled; owner-approved contracts for core and Spark outputs.

Exit: Core/Spark replacements pass keyed hashes, null/duplicate checks and scheduling/runtime gates.

Earlier-wave dependencies must pass their exit criteria; same-wave dependencies must be available before each dependent cuts over.

### Scope counts

| Dimension | Value | Count |
|---|---|---:|
| system | powercenter | 18 |
| system | spark | 21 |
| system | teradata | 33 |
| kind | bteq | 12 |
| kind | mapping | 9 |
| kind | session | 9 |
| kind | spark_job | 21 |
| kind | table | 21 |
| target_type | dbt_model | 42 |
| target_type | snowflake_scripting | 12 |
| target_type | snowpark | 18 |

Licence dependencies eligible to free after verified cutover/decommission: powercenter: 18 objects, spark: 21 objects, teradata: 33 objects.
Teradata compute/catalog access, PowerCenter execution and Spark scheduling/compute can be removed only after all dependent consumers and retention obligations are cleared. These are object counts, not additive monetary savings.

### audit

- **01_load_events** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.01_LOAD_EVENTS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.AUDIT_EVENT (wave 2), SFX_AUDIT.STG_AUDIT_EVENT (wave 1)
- **02_load_controls** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.02_LOAD_CONTROLS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.ACCESS_REVIEW (wave 2), SFX_AUDIT.COMPLIANCE_FLAG (wave 2), SFX_AUDIT.DATA_EXPORT_REQ (wave 2), SFX_AUDIT.RETENTION_POLICY (wave 2), SFX_AUDIT.STG_ACCESS_REVIEW (wave 1), SFX_AUDIT.STG_COMPLIANCE_FLAG (wave 1), SFX_AUDIT.STG_DATA_EXPORT_REQ (wave 1), SFX_AUDIT.STG_RETENTION_POLICY (wave 1)
- **10_summary_daily** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.10_SUMMARY_DAILY`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_AUDIT.ACCESS_REVIEW** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__access_review`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_load_controls (wave 2)
- **SFX_AUDIT.AUDIT_EVENT** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__audit_event`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 01_load_events (wave 2), m_SFX_AUDIT_EVENT (wave 2)
- **SFX_AUDIT.COMPLIANCE_FLAG** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__compliance_flag`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_load_controls (wave 2)
- **SFX_AUDIT.DATA_EXPORT_REQ** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__data_export_req`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_load_controls (wave 2)
- **SFX_AUDIT.RETENTION_POLICY** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__retention_policy`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_load_controls (wave 2)
- **audit_actor_activity_join** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__audit_actor_activity_join`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **audit_archive_resort** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__audit_archive_resort`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **audit_daily_summary** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__audit_daily_summary`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **compliance_flag_rules** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__compliance_flag_rules`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_AUDIT_DAILY_SUMMARY** — @otterworks/data-platform; powercenter/mapping; snowpark → `TRANSFORM.M_SFX_AUDIT_DAILY_SUMMARY`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.AUDIT_EVENT (wave 2)
- **m_SFX_AUDIT_EVENT** — @otterworks/data-platform; powercenter/mapping; dbt_model → `core_audit__m_sfx_audit_event`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.STG_AUDIT_EVENT (wave 1)
- **m_SFX_SECURITY_ALERT** — @otterworks/data-platform; powercenter/mapping; dbt_model → `core_audit__m_sfx_security_alert`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_AUDIT_DAILY_SUMMARY** — @otterworks/data-platform; powercenter/session; dbt_model → `core_audit__s_m_sfx_audit_daily_summary`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_AUDIT_DAILY_SUMMARY (wave 2)
- **s_m_SFX_AUDIT_EVENT** — @otterworks/data-platform; powercenter/session; dbt_model → `core_audit__s_m_sfx_audit_event`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_AUDIT_EVENT (wave 2)
- **s_m_SFX_SECURITY_ALERT** — @otterworks/data-platform; powercenter/session; dbt_model → `core_audit__s_m_sfx_security_alert`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_SECURITY_ALERT (wave 2)
- **security_alert_anomaly** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__security_alert_anomaly`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
### documents

- **01_load_folders** — @otterworks/analytics; teradata/bteq; snowflake_scripting → `OPS.01_LOAD_FOLDERS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.DOCUMENT (wave 2), SFX_DOCUMENTS.FOLDER (wave 2), SFX_DOCUMENTS.STG_DOCUMENT (wave 1), SFX_DOCUMENTS.STG_FOLDER (wave 1)
- **02_current_versions** — @otterworks/analytics; teradata/bteq; snowflake_scripting → `OPS.02_CURRENT_VERSIONS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.DOC_VERSION (wave 2), SFX_DOCUMENTS.STG_DOC_VERSION (wave 1)
- **03_load_access** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.03_LOAD_ACCESS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.DOC_SHARE (wave 2), SFX_DOCUMENTS.DOC_TAG (wave 2), SFX_DOCUMENTS.STG_DOC_SHARE (wave 1), SFX_DOCUMENTS.STG_DOC_TAG (wave 1)
- **04_load_objects** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.04_LOAD_OBJECTS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.DOC_COMMENT (wave 2), SFX_DOCUMENTS.FILE_OBJECT (wave 2), SFX_DOCUMENTS.STG_DOC_COMMENT (wave 1), SFX_DOCUMENTS.STG_FILE_OBJECT (wave 1)
- **05_load_sessions** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.05_LOAD_SESSIONS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.COLLAB_SESSION (wave 2), SFX_DOCUMENTS.STG_COLLAB_SESSION (wave 1), SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY (wave 1), SFX_DOCUMENTS.STORAGE_USAGE_DAILY (wave 2)
- **SFX_DOCUMENTS.COLLAB_SESSION** — @otterworks/data-platform; teradata/table; dbt_model → `core_documents__collab_session`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 05_load_sessions (wave 2)
- **SFX_DOCUMENTS.DOCUMENT** — @otterworks/analytics; teradata/table; dbt_model → `core_documents__document`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 01_load_folders (wave 2), m_SFX_DOCUMENT (wave 2)
- **SFX_DOCUMENTS.DOC_COMMENT** — @otterworks/data-platform; teradata/table; dbt_model → `core_documents__doc_comment`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 04_load_objects (wave 2)
- **SFX_DOCUMENTS.DOC_SHARE** — @otterworks/data-platform; teradata/table; dbt_model → `core_documents__doc_share`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_access (wave 2), m_SFX_DOC_SHARE (wave 2)
- **SFX_DOCUMENTS.DOC_TAG** — @otterworks/data-platform; teradata/table; dbt_model → `core_documents__doc_tag`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_access (wave 2)
- **SFX_DOCUMENTS.DOC_VERSION** — @otterworks/analytics; teradata/table; dbt_model → `core_documents__doc_version`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_current_versions (wave 2)
- **SFX_DOCUMENTS.FILE_OBJECT** — @otterworks/data-platform; teradata/table; dbt_model → `core_documents__file_object`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 04_load_objects (wave 2)
- **SFX_DOCUMENTS.FOLDER** — @otterworks/data-platform; teradata/table; dbt_model → `core_documents__folder`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 01_load_folders (wave 2)
- **SFX_DOCUMENTS.STORAGE_USAGE_DAILY** — @otterworks/data-platform; teradata/table; dbt_model → `core_documents__storage_usage_daily`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 05_load_sessions (wave 2)
- **collab_session_sessionize** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__collab_session_sessionize`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **doc_share_graph_reach** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__doc_share_graph_reach`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **doc_version_diff_stats** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__doc_version_diff_stats`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **docs_event_export_hourly** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__docs_event_export_hourly`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **docs_folder_tree_walk** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__docs_folder_tree_walk`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **docs_search_log_parse** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__docs_search_log_parse`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **docs_share_activity** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__docs_share_activity`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **docs_storage_by_owner** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__docs_storage_by_owner`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **docs_tag_normalize** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__docs_tag_normalize`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **file_object_binary_extract** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__file_object_binary_extract`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_DOCUMENT** — @otterworks/analytics; powercenter/mapping; snowpark → `TRANSFORM.M_SFX_DOCUMENT`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.STG_DOCUMENT (wave 1)
- **m_SFX_DOC_SHARE** — @otterworks/data-platform; powercenter/mapping; snowpark → `TRANSFORM.M_SFX_DOC_SHARE`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_DOCUMENT** — @otterworks/analytics; powercenter/session; dbt_model → `core_documents__s_m_sfx_document`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_DOCUMENT (wave 2)
- **s_m_SFX_DOC_SHARE** — @otterworks/data-platform; powercenter/session; dbt_model → `core_documents__s_m_sfx_doc_share`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_DOC_SHARE (wave 2)
### users

- **01_load_users** — @otterworks/analytics; teradata/bteq; snowflake_scripting → `OPS.01_LOAD_USERS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.APP_USER (wave 2), SFX_USERS.STG_APP_USER (wave 1), SFX_USERS.STG_USER_PROFILE (wave 1), SFX_USERS.USER_PROFILE (wave 2)
- **02_load_teams** — @otterworks/analytics; teradata/bteq; snowflake_scripting → `OPS.02_LOAD_TEAMS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.ROLE_GRANT (wave 2), SFX_USERS.STG_ROLE_GRANT (wave 1), SFX_USERS.STG_TEAM (wave 1), SFX_USERS.STG_TEAM_MEMBER (wave 1), SFX_USERS.TEAM (wave 2), SFX_USERS.TEAM_MEMBER (wave 2)
- **03_load_identity** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.03_LOAD_IDENTITY`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.SSO_IDENTITY (wave 2), SFX_USERS.STG_SSO_IDENTITY (wave 1), SFX_USERS.STG_USER_STATUS_HIST (wave 1), SFX_USERS.USER_STATUS_HIST (wave 2)
- **10_activity_daily** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.10_ACTIVITY_DAILY`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_USERS.APP_USER** — @otterworks/analytics; teradata/table; dbt_model → `core_users__app_user`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 01_load_users (wave 2), m_SFX_APP_USER (wave 2)
- **SFX_USERS.ROLE_GRANT** — @otterworks/data-platform; teradata/table; dbt_model → `core_users__role_grant`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_load_teams (wave 2), m_SFX_ROLE_GRANT (wave 2)
- **SFX_USERS.SSO_IDENTITY** — @otterworks/data-platform; teradata/table; dbt_model → `core_users__sso_identity`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_identity (wave 2)
- **SFX_USERS.TEAM** — @otterworks/analytics; teradata/table; dbt_model → `core_users__team`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_load_teams (wave 2)
- **SFX_USERS.TEAM_MEMBER** — @otterworks/analytics; teradata/table; dbt_model → `core_users__team_member`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 02_load_teams (wave 2), m_SFX_TEAM_MEMBER (wave 2)
- **SFX_USERS.USER_PROFILE** — @otterworks/data-platform; teradata/table; dbt_model → `core_users__user_profile`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 01_load_users (wave 2)
- **SFX_USERS.USER_STATUS_HIST** — @otterworks/data-platform; teradata/table; dbt_model → `core_users__user_status_hist`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_identity (wave 2)
- **m_SFX_APP_USER** — @otterworks/analytics; powercenter/mapping; snowpark → `TRANSFORM.M_SFX_APP_USER`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.STG_APP_USER (wave 1)
- **m_SFX_LOGIN_EVENT** — @otterworks/data-platform; powercenter/mapping; dbt_model → `core_users__m_sfx_login_event`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_ROLE_GRANT** — @otterworks/data-platform; powercenter/mapping; dbt_model → `core_users__m_sfx_role_grant`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_TEAM_MEMBER** — @otterworks/analytics; powercenter/mapping; dbt_model → `core_users__m_sfx_team_member`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_APP_USER** — @otterworks/analytics; powercenter/session; dbt_model → `core_users__s_m_sfx_app_user`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_APP_USER (wave 2)
- **s_m_SFX_LOGIN_EVENT** — @otterworks/data-platform; powercenter/session; dbt_model → `core_users__s_m_sfx_login_event`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_LOGIN_EVENT (wave 2)
- **s_m_SFX_ROLE_GRANT** — @otterworks/data-platform; powercenter/session; dbt_model → `core_users__s_m_sfx_role_grant`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_ROLE_GRANT (wave 2)
- **s_m_SFX_TEAM_MEMBER** — @otterworks/analytics; powercenter/session; dbt_model → `core_users__s_m_sfx_team_member`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: m_SFX_TEAM_MEMBER (wave 2)
- **team_graph_components** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__team_graph_components`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **user_pref_json_flatten** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__user_pref_json_flatten`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **users_active_daily** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__users_active_daily`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **users_login_useragent_parse** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__users_login_useragent_parse`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **users_risk_score** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__users_risk_score`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **users_team_rollup** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__users_team_rollup`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none

## Wave 3

Objects: 58

Entry: Upstream wave 1/2 dependencies passed parity; billing/procedural owners approve financial controls.

Exit: Financial totals, period close, restartability and procedural side effects pass owner sign-off.

Earlier-wave dependencies must pass their exit criteria; same-wave dependencies must be available before each dependent cuts over.

### Scope counts

| Dimension | Value | Count |
|---|---|---:|
| system | powercenter | 12 |
| system | spark | 6 |
| system | teradata | 40 |
| kind | bteq | 13 |
| kind | macro | 5 |
| kind | mapping | 5 |
| kind | procedure | 4 |
| kind | session | 5 |
| kind | spark_job | 6 |
| kind | table | 18 |
| kind | workflow | 1 |
| kind | worklet | 1 |
| target_type | dbt_model | 30 |
| target_type | snowflake_scripting | 24 |
| target_type | snowpark | 4 |

Licence dependencies eligible to free after verified cutover/decommission: powercenter: 12 objects, spark: 6 objects, teradata: 40 objects.
Teradata compute/catalog access, PowerCenter execution and Spark scheduling/compute can be removed only after all dependent consumers and retention obligations are cleared. These are object counts, not additive monetary savings.

### audit

- **03_load_reviews** — @otterworks/finance-reporting; teradata/bteq; snowflake_scripting → `OPS.03_LOAD_REVIEWS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.AUDIT_DAILY_SUMMARY (wave 3), SFX_AUDIT.AUDIT_RECON (wave 3), SFX_AUDIT.LEGAL_HOLD (wave 3), SFX_AUDIT.SECURITY_ALERT (wave 3), SFX_AUDIT.STG_AUDIT_DAILY_SUMMARY (wave 1), SFX_AUDIT.STG_AUDIT_RECON (wave 1), SFX_AUDIT.STG_LEGAL_HOLD (wave 1), SFX_AUDIT.STG_SECURITY_ALERT (wave 1)
- **11_reconciliation** — @otterworks/finance-reporting; teradata/bteq; snowflake_scripting → `OPS.11_RECONCILIATION`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.ACCESS_REVIEW (wave 2), SFX_AUDIT.AUDIT_DAILY_SUMMARY (wave 3), SFX_AUDIT.AUDIT_EVENT (wave 2), SFX_AUDIT.AUDIT_RECON (wave 3), SFX_AUDIT.COMPLIANCE_FLAG (wave 2), SFX_AUDIT.DATA_EXPORT_REQ (wave 2), SFX_AUDIT.LEGAL_HOLD (wave 3), SFX_AUDIT.RETENTION_POLICY (wave 2), SFX_AUDIT.SECURITY_ALERT (wave 3), SFX_AUDIT.STG_ACCESS_REVIEW (wave 1), SFX_AUDIT.STG_AUDIT_DAILY_SUMMARY (wave 1), SFX_AUDIT.STG_AUDIT_EVENT (wave 1), SFX_AUDIT.STG_AUDIT_RECON (wave 1), SFX_AUDIT.STG_COMPLIANCE_FLAG (wave 1), SFX_AUDIT.STG_DATA_EXPORT_REQ (wave 1), SFX_AUDIT.STG_LEGAL_HOLD (wave 1), SFX_AUDIT.STG_RETENTION_POLICY (wave 1), SFX_AUDIT.STG_SECURITY_ALERT (wave 1), SFX_BILLING.BILLING_ADJ (wave 3), SFX_BILLING.CREDIT_NOTE (wave 3), SFX_BILLING.CUSTOMER_ACCOUNT (wave 3), SFX_BILLING.INVOICE_HDR (wave 3), SFX_BILLING.INVOICE_LINE (wave 3), SFX_BILLING.PAYMENT (wave 3), SFX_BILLING.PLAN_CATALOG (wave 3), SFX_BILLING.STG_BILLING_ADJ (wave 1), SFX_BILLING.STG_CREDIT_NOTE (wave 1), SFX_BILLING.STG_CUSTOMER_ACCOUNT (wave 1), SFX_BILLING.STG_INVOICE_HDR (wave 1), SFX_BILLING.STG_INVOICE_LINE (wave 1), SFX_BILLING.STG_PAYMENT (wave 1), SFX_BILLING.STG_PLAN_CATALOG (wave 1), SFX_BILLING.STG_SUBSCRIPTION (wave 1), SFX_BILLING.STG_TAX_RATE (wave 1), SFX_BILLING.STG_USAGE_DAILY (wave 1), SFX_BILLING.SUBSCRIPTION (wave 3), SFX_BILLING.TAX_RATE (wave 3), SFX_BILLING.USAGE_DAILY (wave 3), SFX_DOCUMENTS.COLLAB_SESSION (wave 2), SFX_DOCUMENTS.DOCUMENT (wave 2), SFX_DOCUMENTS.DOC_COMMENT (wave 2), SFX_DOCUMENTS.DOC_SHARE (wave 2), SFX_DOCUMENTS.DOC_TAG (wave 2), SFX_DOCUMENTS.DOC_VERSION (wave 2), SFX_DOCUMENTS.FILE_OBJECT (wave 2), SFX_DOCUMENTS.FOLDER (wave 2), SFX_DOCUMENTS.STG_COLLAB_SESSION (wave 1), SFX_DOCUMENTS.STG_DOCUMENT (wave 1), SFX_DOCUMENTS.STG_DOC_COMMENT (wave 1), SFX_DOCUMENTS.STG_DOC_SHARE (wave 1), SFX_DOCUMENTS.STG_DOC_TAG (wave 1), SFX_DOCUMENTS.STG_DOC_VERSION (wave 1), SFX_DOCUMENTS.STG_FILE_OBJECT (wave 1), SFX_DOCUMENTS.STG_FOLDER (wave 1), SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY (wave 1), SFX_DOCUMENTS.STORAGE_USAGE_DAILY (wave 2), SFX_USERS.APP_USER (wave 2), SFX_USERS.LOGIN_EVENT (wave 3), SFX_USERS.ROLE_GRANT (wave 2), SFX_USERS.SSO_IDENTITY (wave 2), SFX_USERS.STG_APP_USER (wave 1), SFX_USERS.STG_LOGIN_EVENT (wave 1), SFX_USERS.STG_ROLE_GRANT (wave 1), SFX_USERS.STG_SSO_IDENTITY (wave 1), SFX_USERS.STG_TEAM (wave 1), SFX_USERS.STG_TEAM_MEMBER (wave 1), SFX_USERS.STG_USER_ACTIVITY_DAILY (wave 1), SFX_USERS.STG_USER_PROFILE (wave 1), SFX_USERS.STG_USER_STATUS_HIST (wave 1), SFX_USERS.TEAM (wave 2), SFX_USERS.TEAM_MEMBER (wave 2), SFX_USERS.USER_ACTIVITY_DAILY (wave 3), SFX_USERS.USER_PROFILE (wave 2), SFX_USERS.USER_STATUS_HIST (wave 2)
- **SFX_AUDIT.AUDIT_DAILY_SUMMARY** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__audit_daily_summary`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_reviews (wave 3), SFX_AUDIT.P_DAILY_SUMMARY (wave 3), m_SFX_AUDIT_DAILY_SUMMARY (wave 2)
- **SFX_AUDIT.AUDIT_RECON** — @otterworks/finance-reporting; teradata/table; dbt_model → `core_audit__audit_recon`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_reviews (wave 3), 11_reconciliation (wave 3), SFX_AUDIT.P_RECON_COUNTS (wave 3)
- **SFX_AUDIT.LEGAL_HOLD** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__legal_hold`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_reviews (wave 3)
- **SFX_AUDIT.M_RECON_TOTALS** — @otterworks/data-platform; teradata/macro; snowflake_scripting → `OPS.SFX_AUDIT_M_RECON_TOTALS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.AUDIT_RECON (wave 3)
- **SFX_AUDIT.P_DAILY_SUMMARY** — @otterworks/data-platform; teradata/procedure; snowflake_scripting → `OPS.SFX_AUDIT_P_DAILY_SUMMARY`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.AUDIT_DAILY_SUMMARY (wave 3), SFX_AUDIT.AUDIT_EVENT (wave 2)
- **SFX_AUDIT.P_RECON_COUNTS** — @otterworks/data-platform; teradata/procedure; snowflake_scripting → `OPS.SFX_AUDIT_P_RECON_COUNTS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: none
- **SFX_AUDIT.SECURITY_ALERT** — @otterworks/data-platform; teradata/table; dbt_model → `core_audit__security_alert`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 03_load_reviews (wave 3), m_SFX_SECURITY_ALERT (wave 2)
### billing

- **01_load_accounts** — @otterworks/analytics; teradata/bteq; snowflake_scripting → `OPS.01_LOAD_ACCOUNTS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.CUSTOMER_ACCOUNT (wave 3), SFX_BILLING.GL_ACCOUNT (wave 3), SFX_BILLING.PLAN_CATALOG (wave 3), SFX_BILLING.STG_CUSTOMER_ACCOUNT (wave 1), SFX_BILLING.STG_GL_ACCOUNT (wave 1), SFX_BILLING.STG_PLAN_CATALOG (wave 1), SFX_BILLING.STG_TAX_RATE (wave 1), SFX_BILLING.TAX_RATE (wave 3)
- **02_load_subscriptions** — @otterworks/finance-reporting; teradata/bteq; snowflake_scripting → `OPS.02_LOAD_SUBSCRIPTIONS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.STG_SUBSCRIPTION (wave 1), SFX_BILLING.SUBSCRIPTION (wave 3)
- **03_load_invoices** — @otterworks/analytics; teradata/bteq; snowflake_scripting → `OPS.03_LOAD_INVOICES`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.INVOICE_HDR (wave 3), SFX_BILLING.INVOICE_LINE (wave 3), SFX_BILLING.STG_INVOICE_HDR (wave 1), SFX_BILLING.STG_INVOICE_LINE (wave 1)
- **04_load_payments** — @otterworks/billing; teradata/bteq; snowflake_scripting → `OPS.04_LOAD_PAYMENTS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.BILLING_ADJ (wave 3), SFX_BILLING.CREDIT_NOTE (wave 3), SFX_BILLING.PAYMENT (wave 3), SFX_BILLING.STG_BILLING_ADJ (wave 1), SFX_BILLING.STG_CREDIT_NOTE (wave 1), SFX_BILLING.STG_PAYMENT (wave 1)
- **05_load_usage** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.05_LOAD_USAGE`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.STG_USAGE_DAILY (wave 1), SFX_BILLING.USAGE_DAILY (wave 3)
- **10_subscription_report** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.10_SUBSCRIPTION_REPORT`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: none
- **11_currency_daily** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.11_CURRENCY_DAILY`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: none
- **12_invoice_monthly** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.12_INVOICE_MONTHLY`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: none
- **13_period_close** — @otterworks/analytics; teradata/bteq; snowflake_scripting → `OPS.13_PERIOD_CLOSE`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.INVOICE_HDR (wave 3)
- **SFX_BILLING.BILLING_ADJ** — @otterworks/data-platform; teradata/table; dbt_model → `core_billing__billing_adj`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 04_load_payments (wave 3)
- **SFX_BILLING.CREDIT_NOTE** — @otterworks/finance-ops; teradata/table; dbt_model → `core_billing__credit_note`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 04_load_payments (wave 3)
- **SFX_BILLING.CUSTOMER_ACCOUNT** — @otterworks/analytics; teradata/table; dbt_model → `core_billing__customer_account`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 01_load_accounts (wave 3), m_SFX_CUSTOMER_ACCOUNT (wave 3)
- **SFX_BILLING.GL_ACCOUNT** — @otterworks/data-platform; teradata/table; dbt_model → `core_billing__gl_account`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 01_load_accounts (wave 3)
- **SFX_BILLING.GL_JOURNAL_LINE** — @otterworks/finance-ops; teradata/table; dbt_model → `core_billing__gl_journal_line`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.P_MONTHLY_INVOICE (wave 3), m_SFX_GL_JOURNAL_LINE (wave 3)
- **SFX_BILLING.INVOICE_HDR** — @otterworks/analytics; teradata/table; dbt_model → `core_billing__invoice_hdr`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 03_load_invoices (wave 3), 13_period_close (wave 3), SFX_BILLING.P_MONTHLY_INVOICE (wave 3), m_SFX_INVOICE_HDR (wave 3)
- **SFX_BILLING.INVOICE_LINE** — @otterworks/data-platform; teradata/table; dbt_model → `core_billing__invoice_line`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 03_load_invoices (wave 3), 10_storage_monthly (wave 3), SFX_BILLING.P_MONTHLY_INVOICE (wave 3), m_SFX_INVOICE_LINE (wave 3)
- **SFX_BILLING.M_CURRENCY_TOTALS** — @otterworks/data-platform; teradata/macro; snowflake_scripting → `OPS.SFX_BILLING_M_CURRENCY_TOTALS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.INVOICE_HDR (wave 3)
- **SFX_BILLING.M_SUBSCRIPTION_PLANS** — @otterworks/data-platform; teradata/macro; snowflake_scripting → `OPS.SFX_BILLING_M_SUBSCRIPTION_PLANS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.PLAN_CATALOG (wave 3), SFX_BILLING.SUBSCRIPTION (wave 3)
- **SFX_BILLING.PAYMENT** — @otterworks/billing; teradata/table; dbt_model → `core_billing__payment`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 04_load_payments (wave 3), m_SFX_PAYMENT (wave 3)
- **SFX_BILLING.PLAN_CATALOG** — @otterworks/finance-reporting; teradata/table; dbt_model → `core_billing__plan_catalog`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 01_load_accounts (wave 3)
- **SFX_BILLING.P_MONTHLY_INVOICE** — @otterworks/data-platform; teradata/procedure; snowflake_scripting → `OPS.SFX_BILLING_P_MONTHLY_INVOICE`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.BILLING_ADJ (wave 3), SFX_BILLING.CREDIT_NOTE (wave 3), SFX_BILLING.GL_JOURNAL_LINE (wave 3), SFX_BILLING.INVOICE_HDR (wave 3), SFX_BILLING.INVOICE_LINE (wave 3), SFX_BILLING.PLAN_CATALOG (wave 3), SFX_BILLING.SUBSCRIPTION (wave 3), SFX_BILLING.TAX_RATE (wave 3)
- **SFX_BILLING.SUBSCRIPTION** — @otterworks/finance-reporting; teradata/table; dbt_model → `core_billing__subscription`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 02_load_subscriptions (wave 3)
- **SFX_BILLING.TAX_RATE** — @otterworks/data-platform; teradata/table; dbt_model → `core_billing__tax_rate`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 01_load_accounts (wave 3)
- **SFX_BILLING.USAGE_DAILY** — @otterworks/data-platform; teradata/table; dbt_model → `core_billing__usage_daily`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: 05_load_usage (wave 3), 10_storage_monthly (wave 3)
- **billing_churn_score** — @otterworks/data-platform; spark/spark_job; snowpark → `spark__billing_churn_score`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **billing_gl_trial_balance** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__billing_gl_trial_balance`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **billing_invoice_summary_daily** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__billing_invoice_summary_daily`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **billing_payment_aging** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__billing_payment_aging`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.INVOICE_HDR (wave 3), SFX_BILLING.PAYMENT (wave 3)
- **billing_revenue_by_plan** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__billing_revenue_by_plan`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **billing_usage_append_daily** — @otterworks/data-platform; spark/spark_job; dbt_model → `spark__billing_usage_append_daily`.
  - Placement: Spark floor: billing 3, otherwise 2; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_CUSTOMER_ACCOUNT** — @otterworks/analytics; powercenter/mapping; snowpark → `TRANSFORM.M_SFX_CUSTOMER_ACCOUNT`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.STG_CUSTOMER_ACCOUNT (wave 1)
- **m_SFX_GL_JOURNAL_LINE** — @otterworks/finance-ops; powercenter/mapping; snowpark → `TRANSFORM.M_SFX_GL_JOURNAL_LINE`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.STG_INVOICE_HDR (wave 1)
- **m_SFX_INVOICE_HDR** — @otterworks/analytics; powercenter/mapping; snowpark → `TRANSFORM.M_SFX_INVOICE_HDR`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.STG_INVOICE_HDR (wave 1)
- **m_SFX_INVOICE_LINE** — @otterworks/data-platform; powercenter/mapping; dbt_model → `core_billing__m_sfx_invoice_line`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: none
- **m_SFX_PAYMENT** — @otterworks/billing; powercenter/mapping; dbt_model → `core_billing__m_sfx_payment`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: none
- **s_m_SFX_CUSTOMER_ACCOUNT** — @otterworks/analytics; powercenter/session; dbt_model → `core_billing__s_m_sfx_customer_account`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: m_SFX_CUSTOMER_ACCOUNT (wave 3)
- **s_m_SFX_GL_JOURNAL_LINE** — @otterworks/finance-ops; powercenter/session; dbt_model → `core_billing__s_m_sfx_gl_journal_line`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: m_SFX_GL_JOURNAL_LINE (wave 3)
- **s_m_SFX_INVOICE_HDR** — @otterworks/analytics; powercenter/session; dbt_model → `core_billing__s_m_sfx_invoice_hdr`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: m_SFX_INVOICE_HDR (wave 3)
- **s_m_SFX_INVOICE_LINE** — @otterworks/data-platform; powercenter/session; dbt_model → `core_billing__s_m_sfx_invoice_line`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: m_SFX_INVOICE_LINE (wave 3)
- **s_m_SFX_PAYMENT** — @otterworks/billing; powercenter/session; dbt_model → `core_billing__s_m_sfx_payment`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: m_SFX_PAYMENT (wave 3)
- **wf_SFX_BILLING_DAILY** — @otterworks/data-platform; powercenter/workflow; snowflake_scripting → `OPS.WF_SFX_BILLING_DAILY`.
  - Placement: orchestration: billing 3, otherwise 4; final wave = max(floor, upstream waves). Dependencies: s_m_SFX_GL_JOURNAL_LINE (wave 3), s_m_SFX_INVOICE_HDR (wave 3), s_m_SFX_INVOICE_LINE (wave 3), s_m_SFX_PAYMENT (wave 3), wklt_SFX_BILLING_STAGE (wave 3)
- **wklt_SFX_BILLING_STAGE** — @otterworks/data-platform; powercenter/worklet; snowflake_scripting → `OPS.WKLT_SFX_BILLING_STAGE`.
  - Placement: orchestration: billing 3, otherwise 4; final wave = max(floor, upstream waves). Dependencies: s_m_SFX_CUSTOMER_ACCOUNT (wave 3), s_m_SFX_STG_CUSTOMER_ACCOUNT (wave 1), s_m_SFX_STG_INVOICE_HDR (wave 1)
### documents

- **10_storage_monthly** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.10_STORAGE_MONTHLY`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.INVOICE_HDR (wave 3), SFX_BILLING.INVOICE_LINE (wave 3), SFX_BILLING.SUBSCRIPTION (wave 3), SFX_BILLING.USAGE_DAILY (wave 3), SFX_DOCUMENTS.STORAGE_USAGE_DAILY (wave 2)
- **SFX_DOCUMENTS.M_STORAGE_TOTALS** — @otterworks/data-platform; teradata/macro; snowflake_scripting → `OPS.SFX_DOCUMENTS_M_STORAGE_TOTALS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.STORAGE_USAGE_DAILY (wave 2)
### users

- **04_load_events** — @otterworks/data-platform; teradata/bteq; snowflake_scripting → `OPS.04_LOAD_EVENTS`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.LOGIN_EVENT (wave 3), SFX_USERS.STG_LOGIN_EVENT (wave 1), SFX_USERS.STG_USER_ACTIVITY_DAILY (wave 1), SFX_USERS.USER_ACTIVITY_DAILY (wave 3)
- **SFX_USERS.LOGIN_EVENT** — @otterworks/data-platform; teradata/table; dbt_model → `core_users__login_event`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 04_load_events (wave 3), m_SFX_LOGIN_EVENT (wave 2)
- **SFX_USERS.M_TEAM_COUNTS** — @otterworks/data-platform; teradata/macro; snowflake_scripting → `OPS.SFX_USERS_M_TEAM_COUNTS`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.TEAM (wave 2), SFX_USERS.TEAM_MEMBER (wave 2)
- **SFX_USERS.P_ACTIVITY_DAILY** — @otterworks/data-platform; teradata/procedure; snowflake_scripting → `OPS.SFX_USERS_P_ACTIVITY_DAILY`.
  - Placement: billing or procedural workload: wave 3; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.LOGIN_EVENT (wave 3), SFX_USERS.USER_ACTIVITY_DAILY (wave 3)
- **SFX_USERS.USER_ACTIVITY_DAILY** — @otterworks/data-platform; teradata/table; dbt_model → `core_users__user_activity_daily`.
  - Placement: core/relational transformation floor: wave 2; final wave = max(floor, upstream waves). Dependencies: 04_load_events (wave 3), SFX_USERS.P_ACTIVITY_DAILY (wave 3)

## Wave 4

Objects: 11

Entry: Upstream outputs reconciled; consumer owners approve compatibility and orchestration contracts.

Exit: Consumer UAT, compatibility queries, schedules and rollback pass; monitor before disabling legacy access.

Earlier-wave dependencies must pass their exit criteria; same-wave dependencies must be available before each dependent cuts over.

### Scope counts

| Dimension | Value | Count |
|---|---|---:|
| system | powercenter | 2 |
| system | teradata | 9 |
| kind | view | 9 |
| kind | workflow | 2 |
| target_type | compatibility_view | 9 |
| target_type | snowflake_scripting | 2 |

Licence dependencies eligible to free after verified cutover/decommission: powercenter: 2 objects, teradata: 9 objects.
Teradata compute/catalog access, PowerCenter execution and Spark scheduling/compute can be removed only after all dependent consumers and retention obligations are cleared. These are object counts, not additive monetary savings.

### audit

- **SFX_AUDIT.V_CUSTOMER_RECON** — @otterworks/finance-reporting; teradata/view; compatibility_view → `COMPAT.SFX_AUDIT__V_CUSTOMER_RECON`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.AUDIT_RECON (wave 3)
- **SFX_AUDIT.V_EVENT_ACTORS** — @otterworks/data-platform; teradata/view; compatibility_view → `COMPAT.SFX_AUDIT__V_EVENT_ACTORS`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_AUDIT.AUDIT_EVENT (wave 2), SFX_USERS.APP_USER (wave 2)
- **wf_SFX_AUDIT_DAILY** — @otterworks/data-platform; powercenter/workflow; snowflake_scripting → `OPS.WF_SFX_AUDIT_DAILY`.
  - Placement: orchestration: billing 3, otherwise 4; final wave = max(floor, upstream waves). Dependencies: s_m_SFX_AUDIT_DAILY_SUMMARY (wave 2), s_m_SFX_AUDIT_EVENT (wave 2), s_m_SFX_SECURITY_ALERT (wave 2), s_m_SFX_STG_AUDIT_EVENT (wave 1)
### billing

- **SFX_BILLING.V_ACCOUNT_INVOICES** — @otterworks/analytics; teradata/view; compatibility_view → `COMPAT.SFX_BILLING__V_ACCOUNT_INVOICES`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.CUSTOMER_ACCOUNT (wave 3), SFX_BILLING.INVOICE_HDR (wave 3)
- **SFX_BILLING.V_INVOICE_BASE** — @otterworks/analytics; teradata/view; compatibility_view → `COMPAT.SFX_BILLING__V_INVOICE_BASE`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.V_ACCOUNT_INVOICES (wave 4)
- **SFX_BILLING.V_INVOICE_REVENUE** — @otterworks/analytics; teradata/view; compatibility_view → `COMPAT.SFX_BILLING__V_INVOICE_REVENUE`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.V_INVOICE_BASE (wave 4)
- **SFX_BILLING.V_SUBSCRIPTION_PLANS** — @otterworks/finance-reporting; teradata/view; compatibility_view → `COMPAT.SFX_BILLING__V_SUBSCRIPTION_PLANS`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_BILLING.PLAN_CATALOG (wave 3), SFX_BILLING.SUBSCRIPTION (wave 3)
### content

- **wf_SFX_CONTENT_DAILY** — @otterworks/data-platform; powercenter/workflow; snowflake_scripting → `OPS.WF_SFX_CONTENT_DAILY`.
  - Placement: orchestration: billing 3, otherwise 4; final wave = max(floor, upstream waves). Dependencies: s_m_SFX_APP_USER (wave 2), s_m_SFX_DOCUMENT (wave 2), s_m_SFX_DOC_SHARE (wave 2), s_m_SFX_LOGIN_EVENT (wave 2), s_m_SFX_ROLE_GRANT (wave 2), s_m_SFX_STG_APP_USER (wave 1), s_m_SFX_STG_DOCUMENT (wave 1), s_m_SFX_TEAM_MEMBER (wave 2)
### documents

- **SFX_DOCUMENTS.V_DOCUMENT_VERSIONS** — @otterworks/analytics; teradata/view; compatibility_view → `COMPAT.SFX_DOCUMENTS__V_DOCUMENT_VERSIONS`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.DOCUMENT (wave 2), SFX_DOCUMENTS.DOC_VERSION (wave 2)
- **SFX_DOCUMENTS.V_WORKSPACE_STORAGE** — @otterworks/analytics; teradata/view; compatibility_view → `COMPAT.SFX_DOCUMENTS__V_WORKSPACE_STORAGE`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_DOCUMENTS.V_DOCUMENT_VERSIONS (wave 4)
### users

- **SFX_USERS.V_TEAM_MEMBERS** — @otterworks/analytics; teradata/view; compatibility_view → `COMPAT.SFX_USERS__V_TEAM_MEMBERS`.
  - Placement: compatibility serving views: wave 4; final wave = max(floor, upstream waves). Dependencies: SFX_USERS.APP_USER (wave 2), SFX_USERS.TEAM (wave 2), SFX_USERS.TEAM_MEMBER (wave 2)

## Review before cutover

### Stale: owner review, not automatic retirement

- **SFX_AUDIT.V_CUSTOMER_RECON** — @otterworks/finance-reporting; last read=2026-08-12 06:07:11; reads=1; last write=None; recent accesses=[{"QueryID": "111000000069", "principal": "svc_report_recon", "timestamp": "2026-08-12 06:07:11", "usage_type": "READ"}]
- **SFX_BILLING.V_SUBSCRIPTION_PLANS** — @otterworks/finance-reporting; last read=2026-08-12 06:08:36; reads=1; last write=None; recent accesses=[{"QueryID": "111000000070", "principal": "svc_report_recon", "timestamp": "2026-08-12 06:08:36", "usage_type": "READ"}]

### Running Spark jobs without a legacy output reader

Confirm demand with the owner before building a replacement; no reader found is not proof of no consumer.

- **audit_actor_activity_join** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:25:04.607Z; excluded mentions=1 (see manifest evidence).
- **audit_archive_resort** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:29:10.674Z; excluded mentions=1 (see manifest evidence).
- **billing_churn_score** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:26:04.511Z; excluded mentions=1 (see manifest evidence).
- **billing_gl_trial_balance** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:25:16.685Z; excluded mentions=1 (see manifest evidence).
- **billing_invoice_summary_daily** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:23:23.633Z; excluded mentions=1 (see manifest evidence).
- **billing_payment_aging** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:23:41.927Z; excluded mentions=1 (see manifest evidence).
- **billing_revenue_by_plan** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:23:34.584Z; excluded mentions=1 (see manifest evidence).
- **billing_usage_append_daily** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:23:52.055Z; excluded mentions=1 (see manifest evidence).
- **collab_session_sessionize** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:28:20.320Z; excluded mentions=1 (see manifest evidence).
- **compliance_flag_rules** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:29:29.185Z; excluded mentions=1 (see manifest evidence).
- **doc_share_graph_reach** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:28:07.603Z; excluded mentions=1 (see manifest evidence).
- **doc_version_diff_stats** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:28:30.201Z; excluded mentions=1 (see manifest evidence).
- **docs_folder_tree_walk** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:27:41.786Z; excluded mentions=1 (see manifest evidence).
- **docs_search_log_parse** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:25:39.542Z; excluded mentions=0 (see manifest evidence).
- **docs_share_activity** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:24:11.514Z; excluded mentions=2 (see manifest evidence).
- **docs_storage_by_owner** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:24:02.831Z; excluded mentions=2 (see manifest evidence).
- **docs_tag_normalize** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:25:57.755Z; excluded mentions=0 (see manifest evidence).
- **file_object_binary_extract** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:28:55.796Z; excluded mentions=0 (see manifest evidence).
- **lake_compaction_audit** — @otterworks/data-platform; target=retire; runs=1; last run=2026-11-10T20:27:35.087Z; excluded mentions=0 (see manifest evidence).
- **lake_compaction_documents** — @otterworks/data-platform; target=retire; runs=1; last run=2026-11-10T20:27:08.884Z; excluded mentions=0 (see manifest evidence).
- **security_alert_anomaly** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:26:25.724Z; excluded mentions=1 (see manifest evidence).
- **team_graph_components** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:27:52.721Z; excluded mentions=1 (see manifest evidence).
- **user_pref_json_flatten** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:29:22.410Z; excluded mentions=0 (see manifest evidence).
- **users_active_daily** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:24:27.715Z; excluded mentions=1 (see manifest evidence).
- **users_login_useragent_parse** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:25:47.283Z; excluded mentions=0 (see manifest evidence).
- **users_risk_score** — @otterworks/data-platform; target=snowpark; runs=1; last run=2026-11-10T20:26:13.032Z; excluded mentions=1 (see manifest evidence).
- **users_team_rollup** — @otterworks/data-platform; target=dbt_model; runs=1; last run=2026-11-10T20:24:37.269Z; excluded mentions=1 (see manifest evidence).

### Open finding: file_object_binary_extract

`ModuleNotFoundError: No module named warehouse` during the local 2026-11-19 run. `common/binary_documents.py` imports `warehouse.run_config`, which is absent from common.zip and Spark service mounts. Estate source is unchanged. Owner: @otterworks/data-platform. Resolve deployment packaging and rerun before cutover; packaged history does not validate this local failure.
