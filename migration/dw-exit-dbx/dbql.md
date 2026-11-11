# DBQL assessment

25 unread in 90 days: 6 dormant (AccessCount 0, last access 2026-07-01); 19 write-only (recent writes, no reads). Only objects without static code readers are proposed for retirement. Spark landing-feed reads are conservatively treated as logical object readers, not observed JDBC reads.

spark_ref: pr-2740
spark_commit: 40a2465c7eb30777a634abfa698d3a2e7ca17e47
as_of: '2026-11-10'
dead:
  SFX_AUDIT.ACCESS_REVIEW:
    last_access: '2026-11-09 01:01:52'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/02_load_controls.bteq
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
  SFX_AUDIT.AUDIT_EVENT_ARCHIVE:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
    tier: dormant
    code_readers:
    - etl/spark/jobs/py/audit_archive_resort.py
    - warehouse/teradata/macros/archive_overview.sql
  SFX_AUDIT.COMPLIANCE_FLAG:
    last_access: '2026-11-09 01:04:00'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/scala/src/main/scala/sfx/ComplianceFlagRules.scala
    - warehouse/teradata/scripts/audit/02_load_controls.bteq
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
  SFX_AUDIT.DATA_EXPORT_REQ:
    last_access: '2026-11-09 01:03:35'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/02_load_controls.bteq
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
  SFX_AUDIT.LEGAL_HOLD:
    last_access: '2026-11-09 01:06:36'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/03_load_reviews.bteq
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
  SFX_AUDIT.M_ARCHIVE_OVERVIEW:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
    tier: dormant
    code_readers: []
  SFX_AUDIT.RETENTION_POLICY:
    last_access: '2026-11-09 01:02:03'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/02_load_controls.bteq
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
  SFX_AUDIT.SECURITY_ALERT:
    last_access: '2026-11-09 01:05:47'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/jobs/py/security_alert_anomaly.py
    - warehouse/teradata/scripts/audit/03_load_reviews.bteq
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
  SFX_BILLING.STG_GL_JOURNAL_LINE:
    last_access: '2026-11-08 00:36:03'
    access_count: '21'
    tier: write-only
    code_readers: []
  SFX_BILLING.USAGE_DAILY:
    last_access: '2026-11-09 01:19:53'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/jobs/py/billing_usage_append_daily.py
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/billing/05_load_usage.bteq
    - warehouse/teradata/scripts/documents/10_storage_monthly.bteq
  SFX_DOCUMENTS.COLLAB_SESSION:
    last_access: '2026-11-09 01:27:16'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/jobs/py/collab_session_sessionize.py
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/documents/05_load_sessions.bteq
  SFX_DOCUMENTS.DOC_COMMENT:
    last_access: '2026-11-09 01:26:58'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/documents/04_load_objects.bteq
  SFX_DOCUMENTS.DOC_SHARE:
    last_access: '2026-11-09 01:23:09'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/jobs/py/doc_share_graph_reach.py
    - etl/spark/scala/src/main/scala/sfx/DocsShareActivity.scala
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/documents/03_load_access.bteq
  SFX_DOCUMENTS.DOC_TAG:
    last_access: '2026-11-09 01:24:41'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/jobs/py/docs_tag_normalize.py
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/documents/03_load_access.bteq
  SFX_DOCUMENTS.FILE_OBJECT:
    last_access: '2026-11-09 01:25:25'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/jobs/py/docs_storage_by_owner.py
    - etl/spark/jobs/py/file_object_binary_extract.py
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/documents/04_load_objects.bteq
  SFX_DOCUMENTS.FOLDER:
    last_access: '2026-11-09 01:20:47'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/spark/jobs/py/docs_folder_legacy_report.py
    - etl/spark/jobs/py/docs_folder_tree_walk.py
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/documents/01_load_folders.bteq
  SFX_DOCUMENTS.SEARCH_INDEX_LOG:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
    tier: dormant
    code_readers:
    - etl/spark/jobs/py/docs_search_log_parse.py
    - warehouse/teradata/ddl/documents/10_views.sql
  SFX_DOCUMENTS.V_SEARCH_HISTORY:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
    tier: dormant
    code_readers: []
  SFX_USERS.ROLE_GRANT:
    last_access: '2026-11-09 01:33:34'
    access_count: '90'
    tier: write-only
    code_readers:
    - etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOC_SHARE.XML
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/users/02_load_teams.bteq
  SFX_USERS.SSO_IDENTITY:
    last_access: '2026-11-09 01:34:33'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/users/03_load_identity.bteq
  SFX_USERS.STG_USER_PREF:
    last_access: '2026-11-07 00:18:06'
    access_count: '20'
    tier: write-only
    code_readers: []
  SFX_USERS.USER_PREF:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
    tier: dormant
    code_readers:
    - etl/spark/jobs/py/user_pref_json_flatten.py
    - warehouse/teradata/ddl/users/10_views.sql
  SFX_USERS.USER_PROFILE:
    last_access: '2026-11-09 01:30:47'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/users/01_load_users.bteq
  SFX_USERS.USER_STATUS_HIST:
    last_access: '2026-11-09 01:35:05'
    access_count: '90'
    tier: write-only
    code_readers:
    - warehouse/teradata/scripts/audit/11_reconciliation.bteq
    - warehouse/teradata/scripts/users/03_load_identity.bteq
  SFX_USERS.V_USER_SETTINGS:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
    tier: dormant
    code_readers: []
hidden:
- user: FIN_ANALYST_J*****
  queries: 232
  clients:
  - Microsoft Excel; workstation=FIN-WS-014
  apps:
  - ODBC
  first: '2026-08-17 09:14:51'
  last: '2026-11-09 16:21:00'
  objects:
  - SFX_BILLING.GL_ACCOUNT
  - SFX_BILLING.GL_JOURNAL_LINE
  - SFX_BILLING.INVOICE_HDR

Hidden discovery excludes warehouse/teradata/dbql/**, warehouse/teradata/tests/test_dbql.py and this output directory. svc_etl_* are internal producer row-count checks, not consumers; they remain in ETL lineage. The single hidden consumer is FIN_ANALYST_J***** (ODBC/Excel).

Partner SFTP extract svc_partner_sftp IS registered in consumers/registry.yaml with code in consumers/partner-extract. It is not hidden. Registry cadence is nightly 02:15; DBQL instead shows 05:xx reads (timestamps have no timezone, so scheduling/timezone drift requires owner confirmation). Failed read counts below are per user/error/object; multi-object queries contribute to each object.

partner_extract:
  registered: true
  registry: consumers/registry.yaml
  code: consumers/partner-extract
  registry_cadence: nightly 02:15
  query_count: 180
  observed_times:
    05:10: 22
    05:11: 19
    05:12: 17
    05:13: 22
    05:14: 10
    05:17: 18
    05:18: 18
    05:19: 19
    05:20: 23
    05:21: 12
  first: '2026-08-12 05:11:59'
  last: '2026-11-09 05:21:40'
failed_reads:
- user: svc_admin_fin
  error_code: '2616'
  object: SFX_BILLING.INVOICE_HDR
  count: 7
- user: svc_legacy_billing
  error_code: '3807'
  object: SFX_BILLING.INVOICE_EXPORT_QUEUE
  count: 9
