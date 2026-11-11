# DBQL assessment

spark_ref: pr-2740
spark_commit: 40a2465c7eb30777a634abfa698d3a2e7ca17e47
as_of: '2026-11-10'
dead:
  SFX_AUDIT.ACCESS_REVIEW:
    last_access: '2026-11-09 01:01:52'
    access_count: '90'
  SFX_AUDIT.AUDIT_EVENT_ARCHIVE:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
  SFX_AUDIT.COMPLIANCE_FLAG:
    last_access: '2026-11-09 01:04:00'
    access_count: '90'
  SFX_AUDIT.DATA_EXPORT_REQ:
    last_access: '2026-11-09 01:03:35'
    access_count: '90'
  SFX_AUDIT.LEGAL_HOLD:
    last_access: '2026-11-09 01:06:36'
    access_count: '90'
  SFX_AUDIT.M_ARCHIVE_OVERVIEW:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
  SFX_AUDIT.RETENTION_POLICY:
    last_access: '2026-11-09 01:02:03'
    access_count: '90'
  SFX_AUDIT.SECURITY_ALERT:
    last_access: '2026-11-09 01:05:47'
    access_count: '90'
  SFX_BILLING.STG_GL_JOURNAL_LINE:
    last_access: '2026-11-08 00:36:03'
    access_count: '21'
  SFX_BILLING.USAGE_DAILY:
    last_access: '2026-11-09 01:19:53'
    access_count: '90'
  SFX_DOCUMENTS.COLLAB_SESSION:
    last_access: '2026-11-09 01:27:16'
    access_count: '90'
  SFX_DOCUMENTS.DOC_COMMENT:
    last_access: '2026-11-09 01:26:58'
    access_count: '90'
  SFX_DOCUMENTS.DOC_SHARE:
    last_access: '2026-11-09 01:23:09'
    access_count: '90'
  SFX_DOCUMENTS.DOC_TAG:
    last_access: '2026-11-09 01:24:41'
    access_count: '90'
  SFX_DOCUMENTS.FILE_OBJECT:
    last_access: '2026-11-09 01:25:25'
    access_count: '90'
  SFX_DOCUMENTS.FOLDER:
    last_access: '2026-11-09 01:20:47'
    access_count: '90'
  SFX_DOCUMENTS.SEARCH_INDEX_LOG:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
  SFX_DOCUMENTS.V_SEARCH_HISTORY:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
  SFX_USERS.ROLE_GRANT:
    last_access: '2026-11-09 01:33:34'
    access_count: '90'
  SFX_USERS.SSO_IDENTITY:
    last_access: '2026-11-09 01:34:33'
    access_count: '90'
  SFX_USERS.STG_USER_PREF:
    last_access: '2026-11-07 00:18:06'
    access_count: '20'
  SFX_USERS.USER_PREF:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
  SFX_USERS.USER_PROFILE:
    last_access: '2026-11-09 01:30:47'
    access_count: '90'
  SFX_USERS.USER_STATUS_HIST:
    last_access: '2026-11-09 01:35:05'
    access_count: '90'
  SFX_USERS.V_USER_SETTINGS:
    last_access: '2026-07-01 17:30:00'
    access_count: '0'
hidden:
- user: svc_etl_audit
  queries: 90
  clients:
  - etl-audit-01
  apps:
  - BTEQ
  first: '2026-08-12 04:05:28'
  last: '2026-11-09 04:05:57'
  objects:
  - SFX_AUDIT.AUDIT_EVENT
- user: svc_etl_billing
  queries: 90
  clients:
  - etl-billing-01
  apps:
  - BTEQ
  first: '2026-08-12 04:05:01'
  last: '2026-11-09 04:05:01'
  objects:
  - SFX_BILLING.INVOICE_HDR
- user: svc_etl_docs
  queries: 90
  clients:
  - etl-docs-01
  apps:
  - BTEQ
  first: '2026-08-12 04:05:22'
  last: '2026-11-09 04:05:18'
  objects:
  - SFX_DOCUMENTS.DOCUMENT
- user: svc_etl_users
  queries: 90
  clients:
  - etl-users-01
  apps:
  - BTEQ
  first: '2026-08-12 04:05:20'
  last: '2026-11-09 04:05:01'
  objects:
  - SFX_USERS.APP_USER

Dead objects are SFX_* tablesv objects without READ/EXECUTE from queries in [2026-08-12, 2026-11-11). WRITE-only is not use. LastAccessTimeStamp and AccessCount are shown even if they disagree (writes can update them). Hidden users issue SELECT and neither their username nor any observed ClientID occurs in git-tracked repository text excluding DBQL and this output directory. AppID is evidence, not an exclusion key. Registered partner-extract is not hidden: its account is in consumers/registry.yaml. FIN_ANALYST_J***** is NOT hidden under the literal repository-wide rule: warehouse/teradata/tests/test_dbql.py contains its username. This is test evidence, not an operational integration: treat the analyst as an additional discovery risk. Its DBQL evidence is recorded below.

analyst:
  user: FIN_ANALYST_J*****
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
