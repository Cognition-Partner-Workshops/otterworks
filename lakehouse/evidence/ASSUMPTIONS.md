# Migration assumptions

Entries: 63. Validation errors: 0.

## A-001 — PSV empty fields and nulls

**status:** accepted

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Native load-control text alone does not specify the executable emulator's empty-field conversion.

**decision:** Exactly empty non-character fields become null; character empties and whitespace remain strings.

**rationale:** Mirror load_control's COPY write_row conversion and use seed column kinds without duplicating order.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, warehouse/seed/columns.py

## A-002 — Quoted delimiters and multiline records

**status:** accepted

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Native VARTEXT and XML flat-file quoting may differ from Python CSV behavior.

**decision:** Use Python csv.reader with pipe delimiter, including quoted pipes and embedded newlines.

**rationale:** The runnable legacy loader and fixture generator both use Python csv; native PowerCenter declares QUOTE_CHARACTER=NONE and is not the current oracle.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, warehouse/seed/generate.py, etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML

## A-003 — Truncation and CHAR right-padding

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq

**ambiguity:** DDL widths alone do not establish whether INSERT SELECT rejects or truncates overflow.

**decision:** Explicitly truncate text to target width and pad fixed CHAR columns.

**rationale:** Runner.translate wraps inserted text in explicit PostgreSQL casts, which truncate and pad; the pilot mirrors this rather than assuming native Teradata behavior.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/runner.py, warehouse/teradata/ddl/billing/00_tables.sql, warehouse/teradata/scripts/billing/01_load_accounts.bteq

## A-004 — CHAR and VARCHAR represented as STRING

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Spark CTAS does not retain the legacy bounded CHAR/VARCHAR result metadata.

**decision:** Store STRING and implement truncation/padding in model expressions.

**rationale:** Preserves pilot values while acknowledging that schema introspection no longer reports the original text types.

**verification:** billing.customer_account

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/dbt/macros/legacy_text.sql

## A-005 — NOT CASESPECIFIC collation not replicated

**status:** open

**risk:** high

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Legacy comparisons use a case-insensitive collation for selected columns; default Spark strings do not.

**decision:** Do not globally case-fold stored values; leave comparison collation as a documented gap.

**rationale:** The pilot only projects text. Future joins, predicates and grouping need explicit collation decisions.

**verification:** unverified: mixed-case comparisons, grouping and joins have not been ported or parity-tested

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, warehouse/teradata/bteq/bootstrap.sql

## A-006 — Keys and nullability are not transactional constraints

**status:** open

**risk:** high

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Legacy unique primary index and NOT NULL reject writes; dbt data tests run after publication.

**decision:** Use dbt unique/not_null tests, not a claim of transactional rejection.

**rationale:** Normal pilot key parity is checked, but failed builds may already have published invalid data.

**verification:** unverified: transactional duplicate/null-key rejection is not implemented

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/dbt/models/silver/billing/schema.yml

## A-007 — PostgreSQL emulator is the legacy oracle

**status:** accepted

**risk:** high

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Native Teradata, the PostgreSQL interpreter and Informatica represent distinct execution semantics.

**decision:** Treat the executable Teradata-on-PostgreSQL estate as the current parity source of truth.

**rationale:** The task's runnable baseline is the emulator; its behavior is measurable without native Teradata access.

**verification:** billing.customer_account

**sources:** warehouse/README.md, warehouse/teradata/bteq/runner.py

## A-008 — Native FastLoad and TPT behavior remains untested

**status:** open

**risk:** high

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Control-file syntax does not prove native client null, quoting or failure semantics.

**decision:** Mark staging loads as platform-replaced only relative to the local emulator.

**rationale:** No native FastLoad/TPT runtime has been exercised; do not claim vendor-runtime parity.

**verification:** unverified: no native FastLoad/TPT execution has been performed

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/load/fastload/billing_customer_account.fl

## A-009 — Atomicity is per table and business date

**status:** accepted

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** A logical batch spans many independently committed staging loads.

**decision:** Use one Delta overwrite transaction per table/date, not a cross-table batch transaction.

**rationale:** Legacy load_control also uses a transaction per table; partial whole-batch failures remain possible.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/jobs/daily_chain

## A-010 — Bronze retains date-partitioned history

**status:** accepted

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Legacy staging truncates the whole table; retaining multiple dates changes staging lifetime.

**decision:** Replace only the requested _business_date partition and retain other dates.

**rationale:** Date-scoped idempotency is required; downstream models must explicitly select the intended snapshot.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, lakehouse/runtime/ingest.py

## A-011 — Ingest buffers a complete file in memory

**status:** open

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** The legacy COPY loop streams rows; the initial Spark loader collects a file before writing.

**decision:** Buffer one landing file in driver Python memory.

**rationale:** Keeps Python CSV fidelity for the foundation; this is not a production-scale distributed loader.

**verification:** unverified: maximum practical ingest file size has not been benchmarked

**sources:** warehouse/teradata/bteq/load.py, lakehouse/runtime/ingest.py

## A-012 — Parity collects and sorts full datasets

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Production-scale joins/hashes cannot be inferred from a demo-sized Python comparison.

**decision:** Collect both result sets and sort normalized values in memory.

**rationale:** Allows deterministic diagnostics at demo sizes, with an explicit memory and O(n log n) sorting limit.

**verification:** test:lakehouse/tests/test_parity.py::test_equal_order_independent_and_fingerprints

**sources:** warehouse/teradata/scripts/billing/01_load_accounts.bteq, lakehouse/parity/engine.py, lakehouse/parity/readers.py

## A-013 — Hive incompatible-type metadata check disabled

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Delta replacement triggered Hive's incompatible customer_id metadata check before Spark's successful fallback.

**decision:** Set spark.hadoop.hive.metastore.disallow.incompatible.col.type.changes=false for the embedded metastore.

**rationale:** Avoids a reproduced Hive-only compatibility error; Delta schema validation remains authoritative.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_parity_spark_readers

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/runtime/session.py

## A-014 — Delete-all Type-1 account snapshot reload

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq

**ambiguity:** Type-1 could mean merge/update, but this BTEQ deletes the entire account table.

**decision:** Materialize the selected business-date snapshot as a full table replacement, without deduplication or enrichment.

**rationale:** Matches DELETE FROM CUSTOMER_ACCOUNT followed by INSERT SELECT staging; not the separate Informatica mapping's change-update behavior.

**verification:** billing.customer_account

**sources:** warehouse/teradata/scripts/billing/01_load_accounts.bteq, etl/informatica/repository/SFX_BILLING/mappings/m_SFX_CUSTOMER_ACCOUNT.XML

## A-015 — An older selected date replaces current silver

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq

**ambiguity:** Bronze retains snapshots whereas the legacy table exposes only the most recent executed batch.

**decision:** Rebuilding an older date intentionally restores that snapshot as current silver.

**rationale:** Faithful to execution-order Type-1 reload semantics, not a latest-date-wins policy.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/scripts/billing/01_load_accounts.bteq, lakehouse/dbt/models/silver/billing/customer_account.sql

## A-016 — Empty snapshots clear the selected data

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** An empty file, a missing landing file and an absent bronze date are different states.

**decision:** Empty files clear that bronze partition; missing files fail. A silver query for an absent/empty date produces an empty snapshot.

**rationale:** Mirrors empty staging reload, while refusing to silently treat missing source files as valid inputs.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/scripts/billing/01_load_accounts.bteq

## A-017 — Derby metastore supports one process per namespace

**status:** accepted

**risk:** med

**legacy_objects:** batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** The legacy database supports concurrent clients; embedded Derby locks its local database.

**decision:** Require serialized Spark/dbt/parity processes per NS; use separate namespaces for tests.

**rationale:** Persistent namespace-local catalog state is needed across CLI processes without a shared metastore service.

**verification:** unverified: same-namespace concurrency is unsupported and no locking scheduler is implemented

**sources:** warehouse/teradata/docker-compose.teradata.yml, lakehouse/runtime/session.py

## A-018 — Timezone and business-date interpretation

**status:** open

**risk:** med

**legacy_objects:** batch_runner:warehouse/teradata/jobs/daily_chain, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Legacy SQL includes current dates, date arithmetic and host-local timestamps; business date uses YYYYMMDD.

**decision:** Validate explicit YYYYMMDD, run Spark in UTC, and store _business_date as DATE.

**rationale:** Matches the UTC cron host and deterministic fixture date for the pilot; does not migrate all legacy CURRENT_DATE/timestamp logic.

**verification:** unverified: non-UTC timestamps, DST boundaries and non-pilot CURRENT_DATE semantics are not covered

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, warehouse/seed/generate.py, lakehouse/runtime/session.py

## A-019 — Numeric/date conversion deferred to silver

**status:** accepted

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Legacy staging DDL casts typed fields during COPY; raw bronze intentionally does not.

**decision:** Keep source values as strings except null conversion, and cast only in typed models.

**rationale:** Preserves raw source evidence but allows invalid typed values into bronze earlier than the emulator would.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/runtime/ingest.py

## A-020 — Noncanonical cast spellings not proven equivalent

**status:** open

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Spark ANSI and PostgreSQL can accept different numeric/date lexical forms.

**decision:** Use ANSI casts and canonical fixture input rather than permissive try-casts.

**rationale:** Invalid numeric input is tested; exhaustive vendor-specific date/numeric parsing equivalence is not established.

**verification:** unverified: noncanonical dates, whitespace numeric forms and numeric overflow parity are not exhaustively tested

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/bteq/runner.py, lakehouse/runtime/session.py

## A-021 — Staging text widths are not enforced in bronze

**status:** open

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Legacy staging VARCHAR widths can reject or transform oversized source text.

**decision:** Do not enforce staging widths in raw bronze; the pilot applies final target widths.

**rationale:** Bronze is a raw string layer rather than a physical copy of every staging constraint.

**verification:** unverified: overlength staging input above the DDL widths is not parity-tested

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, warehouse/teradata/bteq/load.py

## A-022 — Character sets, compression and physical indexes

**status:** open

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** LATIN/UNICODE flags, COMPRESS and unique primary index encode physical and semantic choices.

**decision:** Do not reproduce encoding restrictions, compression declarations or physical distribution/index metadata.

**rationale:** Delta uses its own storage and indexing; logical collation/constraint gaps are tracked separately.

**verification:** unverified: native LATIN encoding restrictions and physical performance equivalence are not tested

**sources:** warehouse/teradata/ddl/billing/00_tables.sql

## A-023 — Namespaces and medallion paths replace database layout

**status:** accepted

**risk:** low

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Legacy uses SFX_AREA and STG_ names, while the new runtime needs layered schemas and isolated local state.

**decision:** Use lowercase table names in layer_domain databases and .data/NS/delta/layer/domain/table paths.

**rationale:** A direct schema-name copy would not separate bronze, silver and gold; NS is mandatory.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_layout

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, warehouse/seed/columns.py, lakehouse/runtime/layout.py

## A-024 — BTEQ script is only partially migrated

**status:** open

**risk:** high

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq

**ambiguity:** The pilot's BTEQ also reloads plan/tax/GL tables and has branching error labels.

**decision:** Keep the entire BTEQ script pending; only CUSTOMER_ACCOUNT output is converted.

**rationale:** Claiming the whole script converted would conceal unported objects and multi-statement failure semantics.

**verification:** unverified: non-account outputs and BTEQ error-label behavior are not ported

**sources:** warehouse/teradata/scripts/billing/01_load_accounts.bteq

## A-025 — Shared landing files establish comparable inputs

**status:** accepted

**risk:** low

**legacy_objects:** batch_runner:warehouse/teradata/jobs/daily_chain, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Identical seed settings alone do not guarantee both engines consumed identical files.

**decision:** Generate once with legacy-up, then point lakehouse-run at warehouse/landing without regeneration.

**rationale:** The documented Step-2 check consumed the same files with seed 1110, rows 2000 and business date 20261109.

**verification:** billing.customer_account

**sources:** warehouse/seed/generate.py, warehouse/teradata/jobs/daily_chain, lakehouse/README.md

## A-026 — Parity normalization is explicit and column-scoped

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Global trimming, case-folding or empty-to-null could hide genuine data differences.

**decision:** Pilot parity strips only CHAR padding for status, currency and country; other normalization is opt-in per spec.

**rationale:** Avoids treating meaningful account-name whitespace or empty strings as equivalent accidentally.

**verification:** test:lakehouse/tests/test_parity.py::test_normalizations_and_numeric_tolerance

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/parity/specs/billing/customer_account.yaml, lakehouse/parity/engine.py

## A-027 — Duplicate/null parity keys fail without arbitrary pairing

**status:** accepted

**risk:** low

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Duplicate-key rows lack a deterministic one-to-one pairing; a null key cannot reliably identify a row.

**decision:** Fail duplicates/null keys and skip cell comparison within duplicate groups.

**rationale:** Prevents order-dependent pairing from hiding drift; missing/extra and duplicate counts remain exact.

**verification:** test:lakehouse/tests/test_parity.py::test_duplicate_keys

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/parity/engine.py

## A-028 — Numeric normalization and tolerance policy

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Different numeric representations and rounding conventions could alter comparison results.

**decision:** Use finite Decimal values, ROUND_HALF_UP for explicit scale and inclusive absolute per-column tolerance; the pilot has no tolerance.

**rationale:** Money-like fields need declared scale/tolerance rather than implicit float epsilon or global rounding.

**verification:** test:lakehouse/tests/test_parity.py::test_normalizations_and_numeric_tolerance

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/parity/engine.py

## A-029 — Fingerprints are diagnostics, not equality gates

**status:** accepted

**risk:** low

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** A tolerated numeric difference can change a hash or aggregate sum.

**decision:** Compute normalized per-column fingerprints but pass/fail using counts, keys and cell tolerance checks.

**rationale:** Avoids contradictory hash failures for explicitly tolerated cells; hashes do not prove row-level correspondence alone.

**verification:** test:lakehouse/tests/test_parity.py::test_equal_order_independent_and_fingerprints

**sources:** warehouse/teradata/scripts/billing/01_load_accounts.bteq, lakehouse/parity/engine.py

## A-030 — Parity reports are latest-per-spec, not a run archive

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** A single stable evidence path cannot retain every namespace/date/run simultaneously.

**decision:** Overwrite parity/id.json; preserve unselected reports with their own metadata and render all latest saved reports.

**rationale:** Keeps committed evidence small; consumers must read NS/date/timestamp rather than infer all rows are one run.

**verification:** test:lakehouse/tests/test_parity.py::test_specs_and_evidence_failure_exit

**sources:** warehouse/teradata/jobs/daily_chain, lakehouse/parity/__main__.py

## A-031 — Evidence provenance includes dirty worktrees

**status:** accepted

**risk:** low

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Evidence generated before a commit cannot cite that not-yet-existing commit SHA.

**decision:** Record actual HEAD plus git_dirty, spec hash and timestamp; do not rewrite provenance after commit.

**rationale:** The initial Step-2 evidence honestly recorded dirty=true before its implementation commit. Subsequent runs record the actual contemporaneous worktree state, including clean rebased commits.

**verification:** test:lakehouse/tests/test_parity.py::test_specs_and_evidence_failure_exit

**sources:** warehouse/teradata/jobs/daily_chain, lakehouse/evidence/parity/billing.customer_account.json, lakehouse/parity/__main__.py

## A-032 — Local session dbt runner, not a remote service

**status:** accepted

**risk:** med

**legacy_objects:** batch_runner:warehouse/teradata/jobs/daily_chain, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** dbt session mode must reuse the configured Delta/Hive Spark session across worker threads.

**decision:** Initialize Spark in-process before invoking dbtRunner; use one dbt thread and local[2].

**rationale:** A standalone unconfigured dbt invocation would not automatically load Delta jars or the NS metastore.

**verification:** unverified: remote Spark deployments, distributed Airflow executors and concurrent dbt model builds have not been tested

**sources:** warehouse/teradata/jobs/daily_chain, lakehouse/runtime/dbt.py, lakehouse/dbt/profiles.yml

## A-033 — Dependency mirror and offline bootstrap limits

**status:** accepted

**risk:** low

**legacy_objects:** batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** Java Delta jars need a Maven endpoint; the standard endpoints returned HTTP 429 during bootstrap.

**decision:** Use the Google Maven Central mirror as an additional configurable repository with pinned Spark/Delta dependencies.

**rationale:** This is a reproducibility/runtime choice, not a transformation; first startup still needs network access or a warm cache.

**verification:** unverified: fully offline and alternate-platform bootstrap has not been tested

**sources:** warehouse/README.md, lakehouse/runtime/session.py, lakehouse/requirements.txt

## A-034 — Spec trust, connection scope and read-only legacy SQL

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Specs contain executable SQL and paths; namespace names alone do not enforce database endpoint identity.

**decision:** Treat specs as trusted repository code; connect via TD_PG_* with explicit values overriding DSN fields and use read-only PostgreSQL transactions.

**rationale:** Matches documented legacy connection precedence while avoiding interpreter bootstrap mutations during comparison.

**verification:** test:lakehouse/tests/test_parity.py::test_postgres_environment_precedence

**sources:** warehouse/README.md, warehouse/teradata/bteq/runner.py, lakehouse/parity/readers.py

## A-035 — Comparison columns and filters may narrow the claim

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** Common-column defaults and filters can omit schema-only differences or excluded records.

**decision:** Default to common columns, require keys, normalize before symmetric equality/IN filters; pilot explicitly lists all nine output columns and has no filter.

**rationale:** A parity PASS is scoped to the selected columns/rows, not automatically a schema or whole-estate proof.

**verification:** test:lakehouse/tests/test_parity.py::test_null_and_empty_and_filters

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, lakehouse/parity/specs/billing/customer_account.yaml, lakehouse/parity/engine.py

## A-036 — Logical load replacement is not a staging-table conversion

**status:** accepted

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, fastload:warehouse/teradata/load/fastload/users_app_user.fl, fastload:warehouse/teradata/load/fastload/users_login_event.fl, fastload:warehouse/teradata/load/fastload/users_role_grant.fl, fastload:warehouse/teradata/load/fastload/users_sso_identity.fl, fastload:warehouse/teradata/load/fastload/users_team.fl, fastload:warehouse/teradata/load/fastload/users_team_member.fl, fastload:warehouse/teradata/load/fastload/users_user_activity_daily.fl, fastload:warehouse/teradata/load/fastload/users_user_pref.fl, fastload:warehouse/teradata/load/fastload/users_user_profile.fl, fastload:warehouse/teradata/load/fastload/users_user_status_hist.fl, tpt:warehouse/teradata/load/tpt/audit_access_review.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_daily_summary.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_event_archive.tpt, tpt:warehouse/teradata/load/tpt/audit_audit_recon.tpt, tpt:warehouse/teradata/load/tpt/audit_compliance_flag.tpt, tpt:warehouse/teradata/load/tpt/audit_data_export_req.tpt, tpt:warehouse/teradata/load/tpt/audit_legal_hold.tpt, tpt:warehouse/teradata/load/tpt/audit_retention_policy.tpt, tpt:warehouse/teradata/load/tpt/audit_security_alert.tpt, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, tpt:warehouse/teradata/load/tpt/documents_document.tpt, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Bronze ingestion replaces staging transport but does not recreate every STG table's SQL schema or downstream logic.

**decision:** Mark FastLoad/TPT controls replaced_by_platform; leave staging tables, Informatica equivalents and downstream outputs pending.

**rationale:** Prevents inflating converted-object counts from generic ingestion alone.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/jobs/daily_chain

## A-037 — Orchestration is not supplied by Make targets

**status:** open

**risk:** high

**legacy_objects:** batch_runner:warehouse/teradata/jobs/daily_chain, cron_entry:etl/crontab#042e9e7fa551, cron_entry:etl/crontab#06b1c260f55b, cron_entry:etl/crontab#0994e1d7781b, cron_entry:etl/crontab#146d93841612, cron_entry:etl/crontab#21215b59c160, cron_entry:etl/crontab#2ec3f6dad69f, cron_entry:etl/crontab#33854636d6ba, cron_entry:etl/crontab#5c3511fa77a1, cron_entry:etl/crontab#5f21c41e60ca, cron_entry:etl/crontab#69562b8e166b, cron_entry:etl/crontab#6cccad9ba92f, cron_entry:etl/crontab#77635c543e02, cron_entry:etl/crontab#7ce72803f1b1, cron_entry:etl/crontab#8018504ce246, cron_entry:etl/crontab#817f451e90ab, cron_entry:etl/crontab#8256b4d51699, cron_entry:etl/crontab#949f96b6edeb, cron_entry:etl/crontab#9d492d3cabc6, cron_entry:etl/crontab#9f970c1cb2a8, cron_entry:etl/crontab#a1a53c82cfb3, cron_entry:etl/crontab#ae80e15b906a, cron_entry:etl/crontab#afa009bc6185, cron_entry:etl/crontab#b40205d7056e, cron_entry:etl/crontab#b8eef1610f31, cron_entry:etl/crontab#bb89194e6e7e, cron_entry:etl/crontab#d0caaba38c97, cron_entry:etl/crontab#d223b2edaac1, cron_entry:etl/crontab#d28d753c053a, cron_entry:etl/crontab#d379dc30b522, cron_entry:etl/crontab#d54b23093fd1, cron_entry:etl/crontab#d793014c2fb2, cron_entry:etl/crontab#e913aaa5c3d7, cron_entry:etl/crontab#ed928bb7422d, cron_entry:etl/crontab#f34723629b86, cron_entry:etl/crontab#fd7befdb4e7d, cron_entry:warehouse/teradata/jobs/crontab.example#250f291ea0eb, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/01_load_events, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/02_load_controls, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/03_load_reviews, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/10_summary_daily, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/11_reconciliation, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/01_load_accounts, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/02_load_subscriptions, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/03_load_invoices, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/04_load_payments, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/05_load_usage, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/10_subscription_report, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/11_currency_daily, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/12_invoice_monthly, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/13_period_close, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/14_account_history_extract, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/load_account_history, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/01_load_folders, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/02_current_versions, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/03_load_access, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/04_load_objects, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/05_load_sessions, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/10_storage_monthly, cron_entry:warehouse/teradata/jobs/daily_chain#stage=generate, cron_entry:warehouse/teradata/jobs/daily_chain#stage=jobs/reconcile, cron_entry:warehouse/teradata/jobs/daily_chain#stage=setup, cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/01_load_users, cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/02_load_teams, cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/03_load_identity, cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/04_load_events, cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/10_activity_daily

**ambiguity:** Make entry points can execute a batch but do not implement the legacy schedules, retries, dependencies or alerting.

**decision:** Replace only the staging stage with the shared pipeline; retain all unported domain cron entries, other daily-chain stages and the full daily runner as pending.

**rationale:** A partial DAG does not replace legacy domain SQL, reconciliation, exports, alerts or the whole daily chain.

**verification:** unverified: domain-specific scheduling, alerts and whole-estate end-to-end orchestration remain unported

**sources:** etl/crontab, warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain

## A-038 — Fixture-scale pilot is not exhaustive data-domain parity

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** A successful 2000-row sizing fixture cannot establish equivalence for every possible input or adjacent output.

**decision:** Retain explicit unverified/open decisions and only claim account-table parity for the measured fixture.

**rationale:** The fixture includes reserved-edge rows, but performance, production distributions and other domains remain unproven.

**verification:** billing.customer_account

**sources:** warehouse/seed/generate.py, warehouse/seed/columns.py, lakehouse/evidence/parity/billing.customer_account.json

## A-039 — UTC logical date is the date before the run label

**status:** accepted

**risk:** med

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** Airflow cron logical dates label interval starts; this need not be the wall-clock execution date.

**decision:** Use UTC calendar date(logical_date) minus one day for both DAG templates and explicit local business-date mapping. The daily DAG starts at logical date 2026-11-10 and catches up.

**rationale:** Follows the requested contract literally, not data_interval_end minus one day. A scheduled @daily run can therefore process a date two days before its wall-clock trigger.

**verification:** test:lakehouse/tests/test_orchestration.py::test_order_and_logical_business_date

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-040 — Readiness replaces a fixed launch time, not source completeness

**status:** accepted

**risk:** high

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** The UTC cron launches at 01:15 regardless of actual feed arrival. File existence alone cannot prove a writer finished.

**decision:** Start daily at midnight UTC; wait per feed for up to 3600 seconds per attempt, checking every 30 seconds. Accept empty files. Require producers to publish by atomic rename.

**rationale:** Explicit readiness is stronger than a wall-clock assumption, but there is no completeness manifest, nonempty check or size-stability test. Partial published files can still fail ingestion.

**verification:** test:lakehouse/tests/test_orchestration.py::test_readiness_present_empty_missing_and_arriving

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-041 — No-overlap and embedded catalog serialization

**status:** accepted

**risk:** med

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** max_active_runs prevents DAG-run overlap but not parallel tasks or unrelated manual invocations.

**decision:** Use one active run and one active task per DAG; local runs hold a namespace flock and Airflow work tasks take the same lock per task. Do not mix local and Airflow runs in one namespace.

**rationale:** Serial tasks protect Derby; per-task Airflow locks do not implement an across-worker whole-DAG lease. A manual run could start between Airflow tasks.

**verification:** test:lakehouse/tests/test_orchestration.py::test_retries_block_descendants_continue_independent_and_no_overlap

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-042 — Retries and branch-local failure replace stop-at-first-failure

**status:** accepted

**risk:** med

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** The legacy chain returns immediately after its first failed stage and has no built-in retry.

**decision:** Retry seeded tasks once after ten seconds; exhausted tasks block their descendants while independent branches may finish. Both executors return a failed run if a task fails.

**rationale:** Independent domain work need not be discarded because another branch fails. Existing ingestion and full-replacement pilot model are retry-safe; future exports must define idempotence.

**verification:** test:lakehouse/tests/test_orchestration.py::test_retries_block_descendants_continue_independent_and_no_overlap

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-043 — Only the staging orchestration stage is platform-replaced

**status:** accepted

**risk:** high

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** The daily cron and runner invoke many unconverted outputs, not just the pilot and staging loads.

**decision:** Mark only daily_chain#stage=staging as orchestration-replaced; keep the full cron, daily runner, all other stages and domain jobs pending.

**rationale:** The account-loading BTEQ also loads other tables, so even its whole stage cannot be claimed as replaced by the account pilot alone.

**verification:** test:lakehouse/tests/test_orchestration.py::test_pipeline_contract_and_staging_replacement

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-044 — Hourly document export is a paused placeholder

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:docs_event_export_hourly, cron_entry:etl/crontab#06b1c260f55b

**ambiguity:** The legacy document export runs at minute 18 hourly, while the new graph currently has no converted export implementation.

**decision:** Expose a paused @hourly DAG containing one explicitly named no-op stub and no legacy replacement claims.

**rationale:** A scheduling skeleton is not an export conversion. The domain ticket must implement outputs, exact cadence, publication semantics and parity before unpausing.

**verification:** test:lakehouse/tests/test_orchestration.py::test_pipeline_contract_and_staging_replacement

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-045 — Backfill execution does not restore historical legacy state

**status:** open

**risk:** high

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT

**ambiguity:** The pilot PostgreSQL reader selects the current mutable CUSTOMER_ACCOUNT table, not an as-of snapshot.

**decision:** Enable catchup/backfill, retaining date-partitioned bronze inputs, but require matching legacy oracle state or date-specific file specs for historical parity.

**rationale:** A historical lakehouse run can execute correctly and still fail parity against a newer legacy snapshot. No automatic legacy reseeding is performed.

**verification:** unverified: historical as-of PostgreSQL snapshots and multi-date end-to-end backfill parity are not available

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-046 — Local Airflow metadata is not a production service

**status:** open

**risk:** med

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** Production Airflow deployment, multi-worker filesystem visibility and operational alerting are out of scope.

**decision:** Use a separate Python 3.12 venv with official Airflow 2.10.5 constraints, per-namespace SQLite metadata and SequentialExecutor for local DAG tests.

**rationale:** Keeps Airflow dependencies isolated from dbt/PySpark. Airflow and Spark tasks require the same absolute repository/landing paths on this single host; no Docker deployment is added.

**verification:** unverified: production scheduler, distributed workers, external metadata database and alert delivery have not been tested

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-047 — Empty domain selectors do not imply domain conversion

**status:** accepted

**risk:** low

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=staging, batch_runner:warehouse/teradata/jobs/daily_chain

**ambiguity:** Only billing currently has a dbt model, while every domain needs a stable orchestration extension point.

**decision:** Seed tag-based dbt build tasks for all four domains. Empty selections succeed without creating models, and coverage for unconverted outputs stays pending.

**rationale:** Models inherit domain tags and schema/location settings from their silver/gold directories and join the graph automatically. Cross-domain dependencies still require explicit graph edges.

**verification:** test:lakehouse/tests/test_orchestration.py::test_pipeline_contract_and_staging_replacement

**sources:** warehouse/teradata/jobs/crontab.example, warehouse/teradata/jobs/daily_chain, etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-100 — Billing executable numeric and date types

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.ACCOUNT_HIST_BATCH, teradata_table:SFX_BILLING.BILLING_ADJ, teradata_table:SFX_BILLING.CREDIT_NOTE, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT_HIST, teradata_table:SFX_BILLING.GL_ACCOUNT, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.PAYMENT, teradata_table:SFX_BILLING.PLAN_CATALOG, teradata_table:SFX_BILLING.STG_BILLING_ADJ, teradata_table:SFX_BILLING.STG_CREDIT_NOTE, teradata_table:SFX_BILLING.STG_CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_JOURNAL_LINE, teradata_table:SFX_BILLING.STG_INVOICE_HDR, teradata_table:SFX_BILLING.STG_INVOICE_LINE, teradata_table:SFX_BILLING.STG_PAYMENT, teradata_table:SFX_BILLING.STG_PLAN_CATALOG, teradata_table:SFX_BILLING.STG_SUBSCRIPTION, teradata_table:SFX_BILLING.STG_TAX_RATE, teradata_table:SFX_BILLING.STG_USAGE_DAILY, teradata_table:SFX_BILLING.SUBSCRIPTION, teradata_table:SFX_BILLING.TAX_RATE, teradata_table:SFX_BILLING.USAGE_DAILY

**ambiguity:** Bronze strings do not retain Teradata target numeric/date types or native parser behavior.

**decision:** Cast from explicit DDL types in UTC ANSI Spark: BIGINT, INTEGER, DATE, DECIMAL(14,2) and DECIMAL(7,4). Preserve nulls and decimal rounding. Parity certifies canonical fixture inputs; noncanonical vendor parsing remains unverified.

**rationale:** The runnable emulator and DDL are the comparison contract; invalid canonical casts fail rather than silently becoming null.

**verification:** test:lakehouse/tests/test_billing_load.py::test_billing_load_types_empty_and_errors

**sources:** warehouse/teradata/ddl/billing/00_tables.sql, warehouse/teradata/bteq/runner.py, warehouse/seed/columns.py

## A-101 — Billing character widths and collation

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.ACCOUNT_HIST_BATCH, teradata_table:SFX_BILLING.BILLING_ADJ, teradata_table:SFX_BILLING.CREDIT_NOTE, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT_HIST, teradata_table:SFX_BILLING.GL_ACCOUNT, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.PAYMENT, teradata_table:SFX_BILLING.PLAN_CATALOG, teradata_table:SFX_BILLING.STG_BILLING_ADJ, teradata_table:SFX_BILLING.STG_CREDIT_NOTE, teradata_table:SFX_BILLING.STG_CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_JOURNAL_LINE, teradata_table:SFX_BILLING.STG_INVOICE_HDR, teradata_table:SFX_BILLING.STG_INVOICE_LINE, teradata_table:SFX_BILLING.STG_PAYMENT, teradata_table:SFX_BILLING.STG_PLAN_CATALOG, teradata_table:SFX_BILLING.STG_SUBSCRIPTION, teradata_table:SFX_BILLING.STG_TAX_RATE, teradata_table:SFX_BILLING.STG_USAGE_DAILY, teradata_table:SFX_BILLING.SUBSCRIPTION, teradata_table:SFX_BILLING.TAX_RATE, teradata_table:SFX_BILLING.USAGE_DAILY

**ambiguity:** Delta stores strings without native CHAR padding, widths or NOT CASESPECIFIC collation.

**decision:** Replicate explicit PostgreSQL INSERT casts by truncating target text, padding CHAR to its declared width, and retaining null/empty distinctions. Parity strips trailing ASCII spaces only for declared CHAR columns. History change comparison lowercases and removes trailing ASCII spaces; no other load-layer string predicate requires a collation rewrite.

**rationale:** Base INSERT SELECT is explicitly cast by Runner.translate; staging COPY has distinct width-rejection behavior. Equality of history status/currency follows case-insensitive padded legacy values.

**verification:** test:lakehouse/tests/test_billing_load.py::test_billing_history_replay_and_order

**sources:** warehouse/teradata/bteq/runner.py, warehouse/teradata/ddl/billing/00_type2_account.sql, warehouse/teradata/scripts/billing/load_account_history.bteq

## A-102 — Billing FastLoad replacement and staging

**status:** accepted

**risk:** med

**legacy_objects:** fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, teradata_table:SFX_BILLING.STG_BILLING_ADJ, teradata_table:SFX_BILLING.STG_CREDIT_NOTE, teradata_table:SFX_BILLING.STG_CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_JOURNAL_LINE, teradata_table:SFX_BILLING.STG_INVOICE_HDR, teradata_table:SFX_BILLING.STG_INVOICE_LINE, teradata_table:SFX_BILLING.STG_PAYMENT, teradata_table:SFX_BILLING.STG_PLAN_CATALOG, teradata_table:SFX_BILLING.STG_SUBSCRIPTION, teradata_table:SFX_BILLING.STG_TAX_RATE, teradata_table:SFX_BILLING.STG_USAGE_DAILY

**ambiguity:** Native FastLoad sessions, error tables, error limits and parser behavior have no direct Delta equivalent.

**decision:** Replace control execution by existing readiness sensors and CSV bronze ingestion, then typed date-filtered silver staging. Preserve quoted pipes/newlines, exactly-empty noncharacter nulls and character empties. Reject malformed/missing feeds and staging text over 200 characters. Do not implement native FastLoad error tables, session parallelism or partial reject acceptance.

**rationale:** Certify executable emulator load_all/load_control behavior and table parity, not an unavailable proprietary runtime. Existing feeds/sensors already cover all twelve billing inputs.

**verification:** test:lakehouse/tests/test_lakehouse.py::test_ingestion_and_pilot

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/load/fastload/billing_customer_account.fl, warehouse/teradata/ddl/billing/00_tables.sql

## A-103 — Billing snapshot replacement and journal append

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq, bteq_script:warehouse/teradata/scripts/billing/02_load_subscriptions.bteq, bteq_script:warehouse/teradata/scripts/billing/03_load_invoices.bteq, bteq_script:warehouse/teradata/scripts/billing/04_load_payments.bteq, bteq_script:warehouse/teradata/scripts/billing/05_load_usage.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/01_load_accounts, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/02_load_subscriptions, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/03_load_invoices, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/04_load_payments, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/05_load_usage, teradata_table:SFX_BILLING.BILLING_ADJ, teradata_table:SFX_BILLING.CREDIT_NOTE, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.GL_ACCOUNT, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.PAYMENT, teradata_table:SFX_BILLING.PLAN_CATALOG, teradata_table:SFX_BILLING.SUBSCRIPTION, teradata_table:SFX_BILLING.TAX_RATE, teradata_table:SFX_BILLING.USAGE_DAILY

**ambiguity:** Not every billing base table is a current snapshot; GL journal retention is controlled by posting date, not row key.

**decision:** Rebuild eleven current base snapshots only from BUSINESS_DATE. Retain previous GL_JOURNAL_LINE and append staged rows only for posting dates absent in the pre-load journal. Preserve NULL posting-date SQL equality behavior, including repeated append of null-date rows.

**rationale:** Matches DELETE/INSERT in scripts 01..05 and the journal NOT EXISTS POSTING_DT predicate, without deduplication or latest-partition inference.

**verification:** test:lakehouse/tests/test_billing_load.py::test_billing_journal_posting_date_append

**sources:** warehouse/teradata/scripts/billing/01_load_accounts.bteq, warehouse/teradata/scripts/billing/02_load_subscriptions.bteq, warehouse/teradata/scripts/billing/03_load_invoices.bteq, warehouse/teradata/scripts/billing/04_load_payments.bteq, warehouse/teradata/scripts/billing/05_load_usage.bteq

## A-104 — Billing SCD2 replay and ordering

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT_HIST, teradata_table:SFX_BILLING.ACCOUNT_HIST_BATCH, bteq_script:warehouse/teradata/scripts/billing/load_account_history.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/load_account_history

**ambiguity:** A retained bronze snapshot alone cannot express latest-day correction, absent accounts or rejection of completed older dates.

**decision:** Use existing silver history as state. Remove same-day new rows, reopen same-day closures, close changed current status/currency null-safely and insert newly current rows. Retain absent customers. Track even empty or unchanged completed dates in ACCOUNT_HIST_BATCH and reject any run older than its maximum date before either history output is replaced.

**rationale:** Mirrors the reset/MERGE/INSERT/batch sequence in the legacy transaction, including correcting the latest completed file instead of accumulating duplicate versions.

**verification:** test:lakehouse/tests/test_billing_load.py::test_billing_history_replay_and_order

**sources:** warehouse/teradata/scripts/billing/load_account_history.bteq, warehouse/teradata/ddl/billing/00_type2_account.sql

## A-105 — Billing failure and constraint boundary

**status:** open

**risk:** high

**legacy_objects:** teradata_table:SFX_BILLING.ACCOUNT_HIST_BATCH, teradata_table:SFX_BILLING.BILLING_ADJ, teradata_table:SFX_BILLING.CREDIT_NOTE, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT_HIST, teradata_table:SFX_BILLING.GL_ACCOUNT, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.PAYMENT, teradata_table:SFX_BILLING.PLAN_CATALOG, teradata_table:SFX_BILLING.STG_BILLING_ADJ, teradata_table:SFX_BILLING.STG_CREDIT_NOTE, teradata_table:SFX_BILLING.STG_CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_JOURNAL_LINE, teradata_table:SFX_BILLING.STG_INVOICE_HDR, teradata_table:SFX_BILLING.STG_INVOICE_LINE, teradata_table:SFX_BILLING.STG_PAYMENT, teradata_table:SFX_BILLING.STG_PLAN_CATALOG, teradata_table:SFX_BILLING.STG_SUBSCRIPTION, teradata_table:SFX_BILLING.STG_TAX_RATE, teradata_table:SFX_BILLING.STG_USAGE_DAILY, teradata_table:SFX_BILLING.SUBSCRIPTION, teradata_table:SFX_BILLING.TAX_RATE, teradata_table:SFX_BILLING.USAGE_DAILY, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq, bteq_script:warehouse/teradata/scripts/billing/02_load_subscriptions.bteq, bteq_script:warehouse/teradata/scripts/billing/03_load_invoices.bteq, bteq_script:warehouse/teradata/scripts/billing/04_load_payments.bteq, bteq_script:warehouse/teradata/scripts/billing/05_load_usage.bteq, bteq_script:warehouse/teradata/scripts/billing/load_account_history.bteq, fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/01_load_accounts, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/02_load_subscriptions, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/03_load_invoices, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/04_load_payments, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/05_load_usage, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/load_account_history

**ambiguity:** Delta/dbt cannot reproduce every native transactional constraint, BTEQ label, multi-statement partial commit, or the two-table SCD2 transaction.

**decision:** Use atomic per-model Delta replacement, ANSI cast failure and dbt key/null/invariant tests. History validates nonnull unique input keys and older-date guard before mutation; history then batch are ordered and same-date retry-safe. Do not claim cross-model rollback: a failure between history and batch publication, or a post-materialization dbt constraint failure, can leave partial outputs requiring same-date retry and operational review.

**rationale:** Legacy non-history scripts also partially commit, but exact boundaries differ. Cross-table transactional equivalence is not supplied by this foundation; retain this explicit open risk rather than hide it behind row parity.

**verification:** test:lakehouse/tests/test_billing_load.py::test_billing_history_replay_and_order

**sources:** warehouse/teradata/scripts/billing/load_account_history.bteq, warehouse/teradata/scripts/billing/01_load_accounts.bteq, warehouse/teradata/bteq/runner.py

## A-106 — Load-layer parity uses matching legacy stage

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_BILLING.ACCOUNT_HIST_BATCH, teradata_table:SFX_BILLING.BILLING_ADJ, teradata_table:SFX_BILLING.CREDIT_NOTE, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT_HIST, teradata_table:SFX_BILLING.GL_ACCOUNT, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.PAYMENT, teradata_table:SFX_BILLING.PLAN_CATALOG, teradata_table:SFX_BILLING.STG_BILLING_ADJ, teradata_table:SFX_BILLING.STG_CREDIT_NOTE, teradata_table:SFX_BILLING.STG_CUSTOMER_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_ACCOUNT, teradata_table:SFX_BILLING.STG_GL_JOURNAL_LINE, teradata_table:SFX_BILLING.STG_INVOICE_HDR, teradata_table:SFX_BILLING.STG_INVOICE_LINE, teradata_table:SFX_BILLING.STG_PAYMENT, teradata_table:SFX_BILLING.STG_PLAN_CATALOG, teradata_table:SFX_BILLING.STG_SUBSCRIPTION, teradata_table:SFX_BILLING.STG_TAX_RATE, teradata_table:SFX_BILLING.STG_USAGE_DAILY, teradata_table:SFX_BILLING.SUBSCRIPTION, teradata_table:SFX_BILLING.TAX_RATE, teradata_table:SFX_BILLING.USAGE_DAILY, bteq_script:warehouse/teradata/scripts/billing/01_load_accounts.bteq, bteq_script:warehouse/teradata/scripts/billing/02_load_subscriptions.bteq, bteq_script:warehouse/teradata/scripts/billing/03_load_invoices.bteq, bteq_script:warehouse/teradata/scripts/billing/04_load_payments.bteq, bteq_script:warehouse/teradata/scripts/billing/05_load_usage.bteq, bteq_script:warehouse/teradata/scripts/billing/load_account_history.bteq, fastload:warehouse/teradata/load/fastload/billing_billing_adj.fl, fastload:warehouse/teradata/load/fastload/billing_credit_note.fl, fastload:warehouse/teradata/load/fastload/billing_customer_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_account.fl, fastload:warehouse/teradata/load/fastload/billing_gl_journal_line.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_hdr.fl, fastload:warehouse/teradata/load/fastload/billing_invoice_line.fl, fastload:warehouse/teradata/load/fastload/billing_payment.fl, fastload:warehouse/teradata/load/fastload/billing_plan_catalog.fl, fastload:warehouse/teradata/load/fastload/billing_subscription.fl, fastload:warehouse/teradata/load/fastload/billing_tax_rate.fl, fastload:warehouse/teradata/load/fastload/billing_usage_daily.fl, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/01_load_accounts, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/02_load_subscriptions, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/03_load_invoices, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/04_load_payments, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/05_load_usage, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/load_account_history

**ambiguity:** The mutable legacy daily chain later changes invoice headers, lines and GL journal; its final state is not the output of the load layer.

**decision:** Prepare the local legacy billing load baseline by clearing GL journal fixture state and replaying the six scoped BTEQ scripts over unchanged shared landing staging. Compare each of 26 output tables at that load-stage boundary. Do not claim these PASS results certify later monthly billing, period close or historical as-of outputs.

**rationale:** Table parity is meaningful only when both sides represent the same execution stage and prior state. Fresh journal fixture state is used for initial parity; separate stateful tests prove subsequent posting-date retention.

**verification:** billing.gl_journal_line

**sources:** warehouse/teradata/jobs/daily_chain, warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, warehouse/teradata/scripts/billing/13_period_close.bteq

## A-107 — Billing per-stage scheduler replacement

**status:** accepted

**risk:** low

**legacy_objects:** cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/01_load_accounts, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/02_load_subscriptions, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/03_load_invoices, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/04_load_payments, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/05_load_usage, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/load_account_history

**ambiguity:** The all-domain daily runner and its wall-clock scheduling are shared; billing stage replacement cannot claim those global responsibilities.

**decision:** Map only the six scoped billing stage IDs to the tag:billing dbt task after bronze_billing. Model refs order staging and SCD2 batch publication; one parity node per output follows dbt_billing. Shared daily_chain and global cron remain unclaimed.

**rationale:** Existing graph has all twelve billing readiness sensors and domain ingestion. The named contract test checks the exact stage IDs, model presence and parity dependencies.

**verification:** test:lakehouse/tests/test_billing_load.py::test_billing_load_stage_replacement

**sources:** warehouse/teradata/jobs/daily_chain, warehouse/teradata/jobs/crontab.example

## A-108 — Immutable load, monthly and close boundaries

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/10_subscription_report.bteq, bteq_script:warehouse/teradata/scripts/billing/11_currency_daily.bteq, bteq_script:warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, bteq_script:warehouse/teradata/scripts/billing/13_period_close.bteq, bteq_script:warehouse/teradata/scripts/billing/14_account_history_extract.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/10_subscription_report, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/11_currency_daily, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/12_invoice_monthly, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/13_period_close, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/14_account_history_extract, teradata_macro:SFX_BILLING.M_CURRENCY_TOTALS, teradata_macro:SFX_BILLING.M_SUBSCRIPTION_PLANS, teradata_view:SFX_BILLING.V_ACCOUNT_INVOICES, teradata_view:SFX_BILLING.V_INVOICE_BASE, teradata_view:SFX_BILLING.V_INVOICE_REVENUE, teradata_view:SFX_BILLING.V_SUBSCRIPTION_PLANS, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, teradata_procedure:SFX_BILLING.P_MONTHLY_INVOICE

**ambiguity:** Monthly and period-close overwrite the same legacy tables and early reports observe different state from final views.

**decision:** Keep silver load snapshots immutable; gold monthly invoice lines feed monthly header amounts/control totals and journal, then closed_invoice_hdr applies period-close fields. Final views read closed headers. Early currency_daily reads silver. The reporting dbt node follows silver; export stages run in legacy order. Legacy parity fixture snapshots the three load tables and the three monthly tables so all stages can be compared in one run.

**rationale:** Avoid cyclic in-place mutation and preserve Step 2 parity while providing explicit final gold serving surfaces.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_billing_reporting_stage_replacement

**sources:** warehouse/teradata/jobs/daily_chain, warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, warehouse/teradata/scripts/billing/13_period_close.bteq

## A-109 — Monthly procedure joins, dates, decimals and OUT count

**status:** accepted

**risk:** med

**legacy_objects:** teradata_procedure:SFX_BILLING.P_MONTHLY_INVOICE, bteq_script:warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE

**ambiguity:** The monthly procedure has cumulative date predicates, global line deletion, conditional header updates and an OUT parameter.

**decision:** Delete generated descriptions globally, including future invoices; preserve null descriptions. Insert monthly fees and adjustments for invoice_dt <= BUSINESS_DATE, with no adjustment-date or month restriction. Recompute only headers with subscription/plan/tax joins; retain other headers. Use decimal arithmetic and half-up rounding, cast updated targets to DECIMAL(14,2), then compute case-insensitive currency control totals over every header. Expose actual eligible-update count as monthly_invoice_result.n.

**rationale:** Replicate statements rather than infer a conventional current-month billing policy. Capture legacy OUT n from actual procedure log in fixture.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_monthly_states_and_edges

**sources:** warehouse/teradata/procedures/monthly_invoice.sql, warehouse/teradata/ddl/billing/00_tables.sql

## A-110 — Monthly journal replacement and balance

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, teradata_table:SFX_BILLING.GL_JOURNAL_LINE

**ambiguity:** Journal deletion is month-scoped but inserted invoices and credits are cumulative and SQL null predicates matter.

**decision:** Retain journal rows outside the current calendar month, including null posting dates. Regenerate four invoice postings and three eligible credit reversals dated BUSINESS_DATE using legacy numeric IDs and account/sign rules. Null currency cannot join the grouped currency set; null amounts use the original CASE ELSE 0 behavior. Check per-currency debit/credit equality with the same NULL aggregate semantics.

**rationale:** Preserve rerun behavior from an immutable silver prior-state snapshot, not a deduplication/upsert approximation.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_monthly_states_and_edges

**sources:** warehouse/teradata/scripts/billing/12_invoice_monthly.bteq

## A-111 — Period-close date encoding and previous-month window

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/13_period_close.bteq, teradata_table:SFX_BILLING.INVOICE_HDR

**ambiguity:** Teradata date-to-integer arithmetic is not Unix days; PERIOD_START_INT/END_INT refer to the previous calendar month.

**decision:** Apply monthly first. Derive prior date, month number, YYYYMMDD period key and YYYY-MM text for all headers. Set closed=Y only for bill dates in the previous calendar month, retaining other flags. Use explicit BUSINESS_DATE and calendar boundaries, including year/leap transitions.

**rationale:** Matches daily_chain.variables and emulator date_int translation; period-close does not filter the entire header snapshot.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_monthly_states_and_edges

**sources:** warehouse/teradata/jobs/daily_chain, warehouse/teradata/scripts/billing/13_period_close.bteq, warehouse/teradata/bteq/runner.py

## A-112 — DATA/REPORT file contract and atomic publication

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/10_subscription_report.bteq, bteq_script:warehouse/teradata/scripts/billing/11_currency_daily.bteq, bteq_script:warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, bteq_script:warehouse/teradata/scripts/billing/13_period_close.bteq, bteq_script:warehouse/teradata/scripts/billing/14_account_history_extract.bteq

**ambiguity:** Native BTEQ REPORT layout differs from the executable emulator and unordered SQL does not define physical row order.

**decision:** Publish seven actual headerless UTF-8 PSV files with LF records, null as empty and no CSV quoting, matching Runner.render. Use deterministic sorting; compare file rows ignoring unspecified order, declared CHAR trailing blanks and decimal display scale. Case-fold only case-insensitive grouped key representatives. Preserve required invoice/status ordering. Write a same-directory temporary file, fsync and atomic replace per file; empty results publish an empty file. Reject delimiter/newline fields rather than emitting malformed unquoted records.

**rationale:** Certifies emulator files, not proprietary headings/pagination; avoids partially published files and silent stale data on retries.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_report_atomic_publication

**sources:** warehouse/teradata/bteq/runner.py, warehouse/teradata/scripts/billing/10_subscription_report.bteq, warehouse/teradata/scripts/billing/11_currency_daily.bteq, warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, warehouse/teradata/scripts/billing/13_period_close.bteq, warehouse/teradata/scripts/billing/14_account_history_extract.bteq

## A-113 — Reporting collation and inert macro parameters

**status:** open

**risk:** med

**legacy_objects:** teradata_macro:SFX_BILLING.M_CURRENCY_TOTALS, teradata_macro:SFX_BILLING.M_SUBSCRIPTION_PLANS, teradata_view:SFX_BILLING.V_ACCOUNT_INVOICES, teradata_view:SFX_BILLING.V_INVOICE_BASE, teradata_view:SFX_BILLING.V_INVOICE_REVENUE, teradata_view:SFX_BILLING.V_SUBSCRIPTION_PLANS, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, bteq_script:warehouse/teradata/scripts/billing/10_subscription_report.bteq, bteq_script:warehouse/teradata/scripts/billing/11_currency_daily.bteq, bteq_script:warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, bteq_script:warehouse/teradata/scripts/billing/13_period_close.bteq, bteq_script:warehouse/teradata/scripts/billing/14_account_history_extract.bteq, teradata_procedure:SFX_BILLING.P_MONTHLY_INVOICE

**ambiguity:** NOT CASESPECIFIC ICU text and CHAR padding are not native Spark semantics; both macro date parameters are unused.

**decision:** Join plans by lowercase/rtrim and group currencies/status and GL account numbers by lowercase/rtrim, retaining case-sensitive account names. Currency window partitions use the same keys. Choose a deterministic min spelling for group display and normalize only case-insensitive representative fields in parity. Preserve subscription macro s.PLAN_CODE versus view p.PLAN_CODE and do not date-filter either macro. Non-ASCII ICU accent/locale equivalence beyond tested case/trailing-space examples remains unverified.

**rationale:** Avoid duplicate mixed-case currency groups and incorrect window totals; never case-fold case-sensitive descriptions or account names.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_monthly_states_and_edges

**sources:** warehouse/teradata/bteq/bootstrap.sql, warehouse/teradata/bteq/runner.py, warehouse/teradata/macros/currency_totals.sql, warehouse/teradata/macros/subscription_plans.sql, warehouse/teradata/ddl/billing/10_views.sql, warehouse/teradata/ddl/billing/20_views.sql

## A-114 — Reporting failure and publication boundaries

**status:** open

**risk:** high

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/10_subscription_report.bteq, bteq_script:warehouse/teradata/scripts/billing/11_currency_daily.bteq, bteq_script:warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, bteq_script:warehouse/teradata/scripts/billing/13_period_close.bteq, bteq_script:warehouse/teradata/scripts/billing/14_account_history_extract.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/10_subscription_report, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/11_currency_daily, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/12_invoice_monthly, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/13_period_close, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/14_account_history_extract, teradata_macro:SFX_BILLING.M_CURRENCY_TOTALS, teradata_macro:SFX_BILLING.M_SUBSCRIPTION_PLANS, teradata_view:SFX_BILLING.V_ACCOUNT_INVOICES, teradata_view:SFX_BILLING.V_INVOICE_BASE, teradata_view:SFX_BILLING.V_INVOICE_REVENUE, teradata_view:SFX_BILLING.V_SUBSCRIPTION_PLANS, teradata_table:SFX_BILLING.INVOICE_HDR, teradata_table:SFX_BILLING.INVOICE_LINE, teradata_table:SFX_BILLING.GL_JOURNAL_LINE, teradata_procedure:SFX_BILLING.P_MONTHLY_INVOICE

**ambiguity:** Legacy scripts commit mutations and may export before a later balance failure; dbt and independent files cannot provide the same global transaction.

**decision:** Keep A-105 open. Gold tables publish atomically per model; post-build constraints/balance failures block export tasks but may leave some gold outputs. Files publish atomically individually, not as a multi-file transaction. Retries replace rather than append. Do not claim legacy partial-commit ordering, cross-model rollback, native procedure error codes or production cutover safety. Invalid dates and Spark ANSI arithmetic errors fail visibly.

**rationale:** Explicitly retain differing failure boundaries instead of treating fixture row parity as operational equivalence.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_report_atomic_publication

**sources:** warehouse/teradata/scripts/billing/12_invoice_monthly.bteq, warehouse/teradata/scripts/billing/13_period_close.bteq, warehouse/teradata/procedures/monthly_invoice.sql

## A-115 — History extract as-of interval and null groups

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/billing/14_account_history_extract.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=billing/14_account_history_extract

**ambiguity:** History extract reads validity intervals rather than current customer rows and includes null group keys.

**decision:** Filter VALID_FROM_DT <= BUSINESS_DATE < VALID_TO_DT, group status/currency case-insensitively with nulls retained, output BUSINESS_DATE, and sort status/currency NULLS LAST. Serialize nulls as empty fields as the emulator does; the table history itself retains null distinctions.

**rationale:** Do not substitute current account status or infer the newest history date.

**verification:** test:lakehouse/tests/test_billing_reporting.py::test_monthly_states_and_edges

**sources:** warehouse/teradata/scripts/billing/14_account_history_extract.bteq, warehouse/teradata/ddl/billing/00_type2_account.sql
