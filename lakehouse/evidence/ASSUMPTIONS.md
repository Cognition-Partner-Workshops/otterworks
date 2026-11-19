# Migration assumptions

Entries: 141. Validation errors: 0.

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

## A-116 — Separate Informatica overlay and precedence

**status:** accepted

**risk:** med

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** The estate has multiple writers of the same billing tables.

**decision:** Run Informatica after the BTEQ monthly/close states. Treat those states as its explicit prior inputs, then publish independent Informatica Delta targets; never overwrite BTEQ silver/gold. Preserve unmatched prior rows for upserts, truncate only the two staging targets. This defines BTEQ-then-Informatica precedence within an explicitly isolated serving surface, not a retargeting of consumers.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_empty_normal_errors_and_writers

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-117 — Executable reference and independent mapping implementation

**status:** accepted

**risk:** med

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** XML may not describe all executable quirks.

**decision:** Use the existing etl/informatica/runner Integration and MappingRun against an isolated PostgreSQL database with physical types/constraints cloned from legacy and exact prior values frozen before modern mapping execution in inputs/prior.json; execute the actual workflow XML. The frozen BTEQ boundary avoids eight preexisting case-insensitive gold/native journal currency representative differences without normalizing Informatica outputs. Modern code independently implements the billing expression subset and ordered writers; sharing XML metadata, field lists and serialization does not share transformation evaluation. No native PowerCenter certification is claimed.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_native_reject_row_parity

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-118 — Ports, empty values, trimming, defaults and constraints

**status:** accepted

**risk:** med

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** Flat files, transformation ports and physical columns have distinct coercions.

**decision:** Empty flat fields become null; short records supply null and extra fields are ignored like the emulator. Respect source/output string precision, trim ASCII spaces, uppercase only declared expressions and apply NVL only to null, not a post-trim empty string. Numeric conversion accepts the emulator's numeric prefix and rounds half-up. Validate physical integer/decimal/string bounds and non-null identifiers as writer rejects; malformed expression rows are rejected before filters.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_native_reject_row_parity

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-119 — Static lookups, upsert modes and filtered rows

**status:** open

**risk:** med

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** Data-driven lookups are cached before writes; different sessions have different writer modes.

**decision:** Customer/header use static prior-key existence to choose insert/update; repeated new keys can reject instead of dynamically switching to update. Header router rejects missing account/amount/date to DD_REJECT. Invoice line/payment use update-else-insert, retain prior unmatched rows and silently filter the XML null predicates. Preserve line-amount quantity/price fallback. Lookups use case-sensitive first-value matching; ambiguous unordered duplicate lookup selection outside tested ordered inputs remains unverified.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_native_reject_row_parity

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-120 — Informatica GL branches, pre-SQL and persistent sequence

**status:** open

**risk:** high

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** GL is not the BTEQ journal calculation; sequence state is operational input.

**decision:** Delete only no-credit journal rows for nonzero/non-null staged invoice totals, regardless of header router validity. Keep credits/unselected prior rows. Emit AR and deferred-revenue branches, plus tax only when nonzero, using XML lookup accounts and tax rate. Retain negative debit/credit values as expressed. Persist the sequence next value between successful attempts, include each attempt's starting counter in inputs.json and restore that exact counter for native reference execution. Fatal partial-writer sequence persistence is not certified.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_journal_filters_tax_sequence_and_retention

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-121 — Complete target and rejection parity

**status:** accepted

**risk:** med

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** Nullable/duplicate target rows and transformation drops cannot be compared using invented natural keys or only rejection counts.

**decision:** Use typed Delta snapshots for all seven targets, retaining null versus empty and duplicate multiplicity. A canonical all-column ordinal is comparison metadata, not a business key. Compare writer target/record lines exactly as native .bad output; instrument native t_expression to capture removed input contexts without replacing its evaluation. Compare full transformation-rejected rows and counts separately. Reference preparation fails if any native error is not captured. SQL CHAR pad removal is metadata-driven, not general text trimming.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_native_reject_row_parity

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-122 — Workflow failure envelopes and branch reachability

**status:** open

**risk:** high

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** The graph's all-success edges would otherwise suppress an unconditional decision after failed GL.

**decision:** Each real mapping node atomically records native-style status/failure counts and returns a status envelope. Independent validation nodes fail/block stale data parity on mapping errors; the unconditional decision remains reachable and payment checks the true condition before doing work. Worklet failures skip dependent mappings. Final workflow/alert tasks make caught mapping failures observable as pipeline failure. Abrupt process death/SIGKILL can still block descendants and requires platform-level failure monitoring; no atomic multi-target rollback is claimed.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_decision_alert_and_scheduler

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-123 — Actual alert failure/notification path

**status:** open

**risk:** high

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** The legacy emulator only logs an email queue operation, not SMTP delivery.

**decision:** On the false decision branch atomically queue a dated on-call notification with status context and fail the alert task (nonzero exit), never a noop. If SFX_LH_SMTP_HOST is configured, send using SMTP and mark SENT; otherwise the durable outbox plus failed pipeline is the notification handoff. Native subject placeholders are expanded using BUSINESS_DATE. SMTP delivery to a live mail system is unverified; stricter pipeline failure versus legacy successful email enqueue is deliberate.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_decision_alert_and_scheduler

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-124 — Folder scheduler and default session configuration

**status:** open

**risk:** high

**legacy_objects:** informatica_config:SFX_BILLING.default_session_config, informatica_mapping:SFX_BILLING.m_SFX_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_GL_JOURNAL_LINE, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_HDR, informatica_mapping:SFX_BILLING.m_SFX_INVOICE_LINE, informatica_mapping:SFX_BILLING.m_SFX_PAYMENT, informatica_mapping:SFX_BILLING.m_SFX_STG_CUSTOMER_ACCOUNT, informatica_mapping:SFX_BILLING.m_SFX_STG_INVOICE_HDR, informatica_scheduler:SFX_BILLING.wf_SFX_BILLING_DAILY.Scheduler, informatica_session:SFX_BILLING.s_m_SFX_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_GL_JOURNAL_LINE, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_HDR, informatica_session:SFX_BILLING.s_m_SFX_INVOICE_LINE, informatica_session:SFX_BILLING.s_m_SFX_PAYMENT, informatica_session:SFX_BILLING.s_m_SFX_STG_CUSTOMER_ACCOUNT, informatica_session:SFX_BILLING.s_m_SFX_STG_INVOICE_HDR, informatica_source:SFX_BILLING.FF_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.FF_INVOICE_HDR, informatica_source:SFX_BILLING.FF_INVOICE_LINE, informatica_source:SFX_BILLING.FF_PAYMENT, informatica_source:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_source:SFX_BILLING.STG_INVOICE_HDR, informatica_target:SFX_BILLING.CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.GL_JOURNAL_LINE, informatica_target:SFX_BILLING.INVOICE_HDR, informatica_target:SFX_BILLING.INVOICE_LINE, informatica_target:SFX_BILLING.PAYMENT, informatica_target:SFX_BILLING.STG_CUSTOMER_ACCOUNT, informatica_target:SFX_BILLING.STG_INVOICE_HDR, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.Start, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.dec_GL_POSTED, informatica_task:SFX_BILLING.wf_SFX_BILLING_DAILY.em_GL_POSTING_ALERT, informatica_task:SFX_BILLING.wklt_SFX_BILLING_STAGE.Start, informatica_workflow:SFX_BILLING.wf_SFX_BILLING_DAILY, informatica_worklet:SFX_BILLING.wklt_SFX_BILLING_STAGE

**ambiguity:** XML specifies 01:30 daily without a timezone and performance/log settings that the emulator does not fully implement.

**decision:** Use the existing daily UTC logical-date-minus-one scheduler contract, not an additional 01:30 trigger. Its 20261110 start replaces native 20260701; earlier business dates require explicit backfill and available landing inputs, not an automatic historical scheduling claim. Start/worklet/finish nodes validate dates and statuses. Preserve executable Stop-on-errors=0, static lookup caches, per-session processing order and writer flags. Automatic buffers, 512MB tuning, ten-run log retention and native commit intervals are not emulated/certified; modern Delta publication is per target and the ordered writer currently materializes a fixture-sized row set in driver memory. Production scale and failure recovery require review.

**rationale:** Make the converted folder's state, data semantics and operational limits explicit; parity certifies the executable emulator on matched inputs.

**verification:** test:lakehouse/tests/test_billing_informatica.py::test_informatica_decision_alert_and_scheduler

**sources:** etl/informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML, etl/informatica/runner/engine.py, etl/informatica/runner/workflow.py, etl/informatica/runner/expr.py, etl/informatica/params/sfx_d1110_daily.par

## A-125 — Billing Spark alternate wildcard contract

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:billing_invoice_summary_daily, spark_submit:etl/spark/submit/billing_invoice_summary_daily.sh, cron_entry:etl/crontab#d223b2edaac1, spark_job:billing_revenue_by_plan, spark_submit:etl/spark/submit/billing_revenue_by_plan.sh, cron_entry:etl/crontab#8018504ce246, spark_job:billing_payment_aging, spark_submit:etl/spark/submit/billing_payment_aging.sh, cron_entry:etl/crontab#2ec3f6dad69f, spark_job:billing_usage_append_daily, spark_submit:etl/spark/submit/billing_usage_append_daily.sh, cron_entry:etl/crontab#ed928bb7422d, spark_job:billing_gl_trial_balance, spark_submit:etl/spark/submit/billing_gl_trial_balance.sh, cron_entry:etl/crontab#146d93841612, spark_job:billing_churn_score, spark_submit:etl/spark/submit/billing_churn_score.sh, cron_entry:etl/crontab#5f21c41e60ca

**ambiguity:** Headered Spark feeds differ from warehouse columns and may contain multiple dates. Payment aging reads JDBC, not CSV.

**decision:** Use a separate billing-spark/YYYYMMDD bundle with all nine table schemas, exact header/file set and SHA256 manifest. Both engines consume every wildcard PSV. The isolated reference JDBC PAYMENT/INVOICE_HDR tables are loaded from those same files; converted aging reads their frozen file snapshot. Never use billing BTEQ tables for these jobs.

**rationale:** The actual common/schemas.py types and complete multi-file delivery determine inputs; readiness is checked before and after execution. Invalid numeric CSV values retain native permissive null parsing; JDBC snapshots must be valid PostgreSQL typed values.

**verification:** test:lakehouse/tests/test_billing_spark.py::test_billing_spark_input_contract

**sources:** etl/spark/jobs/py/common/runtime.py, etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/billing_invoice_summary_daily.py, etl/spark/jobs/py/billing_revenue_by_plan.py, etl/spark/jobs/py/billing_payment_aging.py, etl/spark/jobs/py/billing_usage_append_daily.py, etl/spark/jobs/py/billing_gl_trial_balance.py, etl/spark/jobs/py/billing_churn_score.py, etl/crontab, etl/spark/submit/billing_invoice_summary_daily.sh, etl/spark/submit/billing_revenue_by_plan.sh, etl/spark/submit/billing_payment_aging.sh, etl/spark/submit/billing_usage_append_daily.sh, etl/spark/submit/billing_gl_trial_balance.sh, etl/spark/submit/billing_churn_score.sh

## A-126 — Billing Spark expression and bag semantics

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:billing_invoice_summary_daily, spark_submit:etl/spark/submit/billing_invoice_summary_daily.sh, cron_entry:etl/crontab#d223b2edaac1, spark_job:billing_revenue_by_plan, spark_submit:etl/spark/submit/billing_revenue_by_plan.sh, cron_entry:etl/crontab#8018504ce246, spark_job:billing_payment_aging, spark_submit:etl/spark/submit/billing_payment_aging.sh, cron_entry:etl/crontab#2ec3f6dad69f, spark_job:billing_usage_append_daily, spark_submit:etl/spark/submit/billing_usage_append_daily.sh, cron_entry:etl/crontab#ed928bb7422d, spark_job:billing_gl_trial_balance, spark_submit:etl/spark/submit/billing_gl_trial_balance.sh, cron_entry:etl/crontab#146d93841612, spark_job:billing_churn_score, spark_submit:etl/spark/submit/billing_churn_score.sh, cron_entry:etl/crontab#5f21c41e60ca

**ambiguity:** SQL joins, nullable keys, decimal aggregates, UDF doubles and max-date filtering must not be replaced by BTEQ meanings.

**decision:** Preserve native inner/left joins, duplicate multiplicity, SUM nulls, GL null-key nonmatches, separate SUM(debit-credit), case-sensitive closed status, Python math.exp, and latest USAGE_DATE across all files even when different from BUSINESS_DATE. Use ANSI=false as native Spark. Parity orders every output column and assigns a row number only in comparison views, retaining nulls and exact duplicate counts.

**rationale:** All six original PySpark scripts execute independently in the oracle; no reference transformation is reimplemented or imported into converted transformations.

**verification:** test:lakehouse/tests/test_billing_spark.py::test_billing_spark_transformations

**sources:** etl/spark/jobs/py/common/runtime.py, etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/billing_invoice_summary_daily.py, etl/spark/jobs/py/billing_revenue_by_plan.py, etl/spark/jobs/py/billing_payment_aging.py, etl/spark/jobs/py/billing_usage_append_daily.py, etl/spark/jobs/py/billing_gl_trial_balance.py, etl/spark/jobs/py/billing_churn_score.py, etl/crontab, etl/spark/submit/billing_invoice_summary_daily.sh, etl/spark/submit/billing_revenue_by_plan.sh, etl/spark/submit/billing_payment_aging.sh, etl/spark/submit/billing_usage_append_daily.sh, etl/spark/submit/billing_gl_trial_balance.sh, etl/spark/submit/billing_churn_score.sh

## A-127 — Billing Spark physical output separation

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:billing_invoice_summary_daily, spark_submit:etl/spark/submit/billing_invoice_summary_daily.sh, cron_entry:etl/crontab#d223b2edaac1, spark_job:billing_revenue_by_plan, spark_submit:etl/spark/submit/billing_revenue_by_plan.sh, cron_entry:etl/crontab#8018504ce246, spark_job:billing_payment_aging, spark_submit:etl/spark/submit/billing_payment_aging.sh, cron_entry:etl/crontab#2ec3f6dad69f, spark_job:billing_usage_append_daily, spark_submit:etl/spark/submit/billing_usage_append_daily.sh, cron_entry:etl/crontab#ed928bb7422d, spark_job:billing_gl_trial_balance, spark_submit:etl/spark/submit/billing_gl_trial_balance.sh, cron_entry:etl/crontab#146d93841612, spark_job:billing_churn_score, spark_submit:etl/spark/submit/billing_churn_score.sh, cron_entry:etl/crontab#5f21c41e60ca

**ambiguity:** Three jobs write both Parquet and JDBC; neither those JDBC schemas nor these feed meanings are the BTEQ outputs.

**decision:** Keep six raw Parquet outputs and three separately persisted Delta replacements for native JDBC outputs, with nine independent actual-output parity specs. No legacy database or downstream consumer is retargeted. Each output exposes a gold_billing comparison view with an added parity-only row number.

**rationale:** Isolated native JDBC target tables and Parquet files are read separately. Consumer cutover and live JDBC publication are not part of this step.

**verification:** billing.spark_billing_gl_trial_balance_jdbc

**sources:** etl/spark/jobs/py/common/runtime.py, etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/billing_invoice_summary_daily.py, etl/spark/jobs/py/billing_revenue_by_plan.py, etl/spark/jobs/py/billing_payment_aging.py, etl/spark/jobs/py/billing_usage_append_daily.py, etl/spark/jobs/py/billing_gl_trial_balance.py, etl/spark/jobs/py/billing_churn_score.py, etl/crontab, etl/spark/submit/billing_invoice_summary_daily.sh, etl/spark/submit/billing_revenue_by_plan.sh, etl/spark/submit/billing_payment_aging.sh, etl/spark/submit/billing_usage_append_daily.sh, etl/spark/submit/billing_gl_trial_balance.sh, etl/spark/submit/billing_churn_score.sh

## A-128 — Billing usage delivery idempotence versus native append

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:billing_invoice_summary_daily, spark_submit:etl/spark/submit/billing_invoice_summary_daily.sh, cron_entry:etl/crontab#d223b2edaac1, spark_job:billing_revenue_by_plan, spark_submit:etl/spark/submit/billing_revenue_by_plan.sh, cron_entry:etl/crontab#8018504ce246, spark_job:billing_payment_aging, spark_submit:etl/spark/submit/billing_payment_aging.sh, cron_entry:etl/crontab#2ec3f6dad69f, spark_job:billing_usage_append_daily, spark_submit:etl/spark/submit/billing_usage_append_daily.sh, cron_entry:etl/crontab#ed928bb7422d, spark_job:billing_gl_trial_balance, spark_submit:etl/spark/submit/billing_gl_trial_balance.sh, cron_entry:etl/crontab#146d93841612, spark_job:billing_churn_score, spark_submit:etl/spark/submit/billing_churn_score.sh, cron_entry:etl/crontab#5f21c41e60ca

**ambiguity:** The native usage job appends duplicates on every invocation, including a replay.

**decision:** Treat business date plus immutable input/code signature as a delivery. Append a new delivery once, preserve duplicates within it, and make identical retries no-ops in both Parquet and Delta. Reject a changed completed append delivery. Distinct business-date deliveries append even if MAX(USAGE_DATE) is unchanged. Non-append jobs overwrite their current snapshot and permit explicit older-date reruns.

**rationale:** The requested retry idempotence intentionally differs from raw native replay; baseline parity compares one invocation. Tests cover native duplicate rows, identical replay, later delivery, old-date replay and changed-delivery rejection.

**verification:** test:lakehouse/tests/test_billing_spark.py::test_billing_spark_append_replay_and_atomic_recovery

**sources:** etl/spark/jobs/py/common/runtime.py, etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/billing_invoice_summary_daily.py, etl/spark/jobs/py/billing_revenue_by_plan.py, etl/spark/jobs/py/billing_payment_aging.py, etl/spark/jobs/py/billing_usage_append_daily.py, etl/spark/jobs/py/billing_gl_trial_balance.py, etl/spark/jobs/py/billing_churn_score.py, etl/crontab, etl/spark/submit/billing_invoice_summary_daily.sh, etl/spark/submit/billing_revenue_by_plan.sh, etl/spark/submit/billing_payment_aging.sh, etl/spark/submit/billing_usage_append_daily.sh, etl/spark/submit/billing_gl_trial_balance.sh, etl/spark/submit/billing_churn_score.sh

## A-129 — Billing Spark cron and submit replacement

**status:** open

**risk:** med

**legacy_objects:** spark_job:billing_invoice_summary_daily, spark_submit:etl/spark/submit/billing_invoice_summary_daily.sh, cron_entry:etl/crontab#d223b2edaac1, spark_job:billing_revenue_by_plan, spark_submit:etl/spark/submit/billing_revenue_by_plan.sh, cron_entry:etl/crontab#8018504ce246, spark_job:billing_payment_aging, spark_submit:etl/spark/submit/billing_payment_aging.sh, cron_entry:etl/crontab#2ec3f6dad69f, spark_job:billing_usage_append_daily, spark_submit:etl/spark/submit/billing_usage_append_daily.sh, cron_entry:etl/crontab#ed928bb7422d, spark_job:billing_gl_trial_balance, spark_submit:etl/spark/submit/billing_gl_trial_balance.sh, cron_entry:etl/crontab#146d93841612, spark_job:billing_churn_score, spark_submit:etl/spark/submit/billing_churn_score.sh, cron_entry:etl/crontab#5f21c41e60ca

**ambiguity:** Six submit wrappers carry cluster resource settings and environment/credential behavior alongside six independent cron times.

**decision:** Replace scheduling with six paused UTC DAGs at the exact original minute/hour. Validate input manifests before readiness, run, then parity. Preserve one active run/task, namespace serialization and retries. Start at the foundation date; earlier dates require explicit backfill. Local two-thread Spark replaces executor/shuffle tuning; do not reproduce embedded wrapper credentials. Supply managed credentials at consumer cutover.

**rationale:** Named tests verify all six cadences and success edges. Native jobs are invoked directly, not wrappers with cluster-specific paths and credential exports. Production sizing, actual scheduler activation and live credential/JDBC wiring remain unverified.

**verification:** test:lakehouse/tests/test_billing_spark.py::test_billing_spark_cron_replacement

**sources:** etl/spark/jobs/py/common/runtime.py, etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/billing_invoice_summary_daily.py, etl/spark/jobs/py/billing_revenue_by_plan.py, etl/spark/jobs/py/billing_payment_aging.py, etl/spark/jobs/py/billing_usage_append_daily.py, etl/spark/jobs/py/billing_gl_trial_balance.py, etl/spark/jobs/py/billing_churn_score.py, etl/crontab, etl/spark/submit/billing_invoice_summary_daily.sh, etl/spark/submit/billing_revenue_by_plan.sh, etl/spark/submit/billing_payment_aging.sh, etl/spark/submit/billing_usage_append_daily.sh, etl/spark/submit/billing_gl_trial_balance.sh, etl/spark/submit/billing_churn_score.sh

## A-130 — Billing Spark publication and recovery boundary

**status:** open

**risk:** high

**legacy_objects:** spark_job:billing_invoice_summary_daily, spark_submit:etl/spark/submit/billing_invoice_summary_daily.sh, cron_entry:etl/crontab#d223b2edaac1, spark_job:billing_revenue_by_plan, spark_submit:etl/spark/submit/billing_revenue_by_plan.sh, cron_entry:etl/crontab#8018504ce246, spark_job:billing_payment_aging, spark_submit:etl/spark/submit/billing_payment_aging.sh, cron_entry:etl/crontab#2ec3f6dad69f, spark_job:billing_usage_append_daily, spark_submit:etl/spark/submit/billing_usage_append_daily.sh, cron_entry:etl/crontab#ed928bb7422d, spark_job:billing_gl_trial_balance, spark_submit:etl/spark/submit/billing_gl_trial_balance.sh, cron_entry:etl/crontab#146d93841612, spark_job:billing_churn_score, spark_submit:etl/spark/submit/billing_churn_score.sh, cron_entry:etl/crontab#5f21c41e60ca

**ambiguity:** Legacy Parquet and JDBC writes can fail independently; append replay may duplicate the successful half.

**decision:** Write immutable Parquet and Delta version directories, validate the original manifest again and atomically replace one POSIX current symlink after both outputs finish. Persist delivery state inside the committed version. Re-register comparison views on retry. Keep failed/orphan versions for inspection. Use the namespace-serialized orchestrator; direct billing CLI calls also take an exclusive billing lock.

**rationale:** Injected commit/input failures prove the previous two-surface publication survives and retry succeeds. This is a local-filesystem contract, not object-store/distributed transaction equivalence. Comparison-view DDL is separately retryable, full-history append rewrites grow over time, orphan cleanup and production-scale recovery remain operational risks.

**verification:** test:lakehouse/tests/test_billing_spark.py::test_billing_spark_append_replay_and_atomic_recovery

**sources:** etl/spark/jobs/py/common/runtime.py, etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/billing_invoice_summary_daily.py, etl/spark/jobs/py/billing_revenue_by_plan.py, etl/spark/jobs/py/billing_payment_aging.py, etl/spark/jobs/py/billing_usage_append_daily.py, etl/spark/jobs/py/billing_gl_trial_balance.py, etl/spark/jobs/py/billing_churn_score.py, etl/crontab, etl/spark/submit/billing_invoice_summary_daily.sh, etl/spark/submit/billing_revenue_by_plan.sh, etl/spark/submit/billing_payment_aging.sh, etl/spark/submit/billing_usage_append_daily.sh, etl/spark/submit/billing_gl_trial_balance.sh, etl/spark/submit/billing_churn_score.sh

## A-131 — Pinned consumer clocks

**status:** accepted

**risk:** med

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** CURRENT_DATE, default run dates and prior-day gates otherwise drift between runs.

**decision:** Business date is the delivered day; default UTC clock is business date plus one day. Optional clock-date overrides are explicit and validated. Calendar arithmetic, strict inequalities and 12-month windows are preserved.

**rationale:** The legacy batch host is UTC and defaults to yesterday; actual source queries execute at both sides of the bill-date and aging boundaries.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_legacy_clock_boundary_and_matching_queries

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-132 — Consumer query source and input precedence

**status:** accepted

**risk:** med

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** Readers span Python, Ruby, Java, Scala and Teradata SQL; rewriting services is prohibited.

**decision:** Extract only the fixed SQL constants and bind validated parameters. Legacy reference runs the actual SQL through Runner; independent SQLGlot AST migration maps to silver billing plus final monthly/closed gold relations. Informatica/Spark targets do not override warehouse consumer inputs. Service query-module bindings are opt-in.

**rationale:** Source-derived SQL prevents hidden query omissions; no services, legacy SQL or source files are modified. The existing 44 warehouse-output parity specs establish matching input states. Both translators share the SQLGlot parser, not the backend rewrite logic; native Teradata is not executed.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_legacy_clock_boundary_and_matching_queries

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-133 — Consumer numeric, collation and bag comparison

**status:** accepted

**risk:** med

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** FORMAT fields, CHAR padding, NOCASE currency groups, nullable keys and decimal division differ by engine.

**decision:** Ignore CHAR right padding; exact cents for money; 1e-6 absolute tolerance only for DSO/open ratio. Case-fold only NOCASE status/currency representatives, never CASESPECIFIC plan names, region or customer names. Comparison-only deterministic ordinals preserve duplicate and null rows. Currency aging groups use lowercase NOCASE keys.

**rationale:** Raw business rows are unchanged except declared code representatives and FORMAT display. Ratio precision differences are bounded explicitly; no financial-cent mismatch is tolerated.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_legacy_clock_boundary_and_matching_queries

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-134 — Billing CSV and service read interfaces

**status:** accepted

**risk:** med

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** Billing export DTO formatting, 100000-row limits and API reads must remain usable without editing services.

**decision:** Expose query(spark,name,business_date,clock,parameters) and preserve all seven service SQL result schemas, filters, limits and ordering. Emit billing CSV with original header, Python CSV quoting, ISO dates, Decimal money and row cap; preserve duplicate invoice rows. Legacy DTO/export function ASTs execute directly as the file oracle.

**rationale:** These replace warehouse read responsibilities and CSV output, not authentication, HTTP routing, caching or unrelated service data. Services can point an adapter to the lakehouse module; automatic production cutover is outside this change.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_invoice_csv_source_and_duplicates

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-135 — Partner validation, publication and simulated transfer

**status:** accepted

**risk:** med

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** Raw REPORT formatting, awk cent arithmetic, duplicate rejection and publication/transfer boundaries need independent coverage.

**decision:** Compare raw rows with exact-cent FORMAT normalization; validate seven fields, duplicate IDs, money and cumulative cent limits; preserve signed zero matching awk. Publish CSV and simulated-transfer receipt through one atomic version pointer. Live SFTP remains unsupported. Choose explicit partner-invoices-YYYYMMDD.csv output paths, as permitted by the legacy CLI optional output argument.

**rationale:** The actual legacy awk and SFTP scripts produce the references. CSV lines include header/trailer. Receipt verifies actual native dry-run put destination and physical payload SHA256/bytes. Unsafe/live-transfer configurations fail before lakehouse publication, stronger than legacy publish-then-transfer failure.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_duplicate_and_atomic_publication_errors

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-136 — BI artifact and workbook feed

**status:** open

**risk:** med

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** Excel Power Query is not available; typed empty fields and workbook grouping need an explicit reference contract.

**decision:** Independently read the actual legacy and lakehouse account-status PSV files with the source PQ four-column UTF-8/date/text/Int64 contract. Empty text remains unknown/null, not zero; publish typed rows and a status/currency count feed.

**rationale:** The actual PQ source and workbook README define the contract. Python readers emulate typed Power Query and workbook aggregation; Excel refresh/rendering and locale-specific behavior are not executed.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_atomic_bytes_and_bi_contract

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-137 — Consumer atomicity and production integration

**status:** open

**risk:** high

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** Retry, process failure, concurrent publication and deployment filesystems differ from the legacy scripts.

**decision:** Private 0600 temporary files, fsync, immutable version directories and atomic local POSIX symlink publication preserve prior files on validation/write/rename errors. A namespace lock serializes the CLI. Partner and other consumer outputs are separate transactions; orphans are retained.

**rationale:** Empty/error and injected-failure tests cover local publication. Object-store publication, cross-worker whole-DAG leases, cleanup, full production volume, driver collection limits and actual consumer configuration rollout require review before cutover.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_duplicate_and_atomic_publication_errors

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-138 — Partner cron and on-demand responsibilities

**status:** open

**risk:** med

**legacy_objects:** bi_artifact:consumers/bi/account_status.pq, bteq_script:consumers/partner-extract/sql/partner_invoice_extract.bteq, consumer:admin-service, consumer:analytics-service, consumer:billing-service, consumer:finance-account-workbook, consumer:legacy-billing, consumer:partner-extract, consumer:report-service, consumer_script:consumers/partner-extract/bin/nightly_extract.sh, consumer_script:consumers/partner-extract/bin/postprocess.sh, consumer_script:consumers/partner-extract/bin/sftp_push.sh, cron_entry:warehouse/teradata/jobs/crontab.example#c583c86ce8ed

**ambiguity:** The owned UTC host cron runs at 02:15 while other readers are on-demand or cached services.

**decision:** Add a paused UTC 15 2 * * * DAG, readiness-gated on the dated closed/history export, running only partner extraction then all three parity specs. Main daily DAG publishes all consumer artifacts after billing gold/history exports. Existing service cache and HTTP schedules are not claimed as migrated.

**rationale:** Cadence, logical-date-minus-one convention, readiness, retries and dependencies are named-test verified. Live scheduling, late-feed behavior, resource sizing and historical backfill coordination still require operational acceptance.

**verification:** test:lakehouse/tests/test_billing_consumers.py::test_consumer_parameters_and_cron_replacement

**sources:** consumers/registry.yaml, consumers/bi/account_status.pq, consumers/bi/README.md, consumers/partner-extract/sql/partner_invoice_extract.bteq, consumers/partner-extract/bin/nightly_extract.sh, consumers/partner-extract/bin/postprocess.sh, consumers/partner-extract/bin/sftp_push.sh, warehouse/teradata/jobs/crontab.example, services/billing-service/app/warehouse/teradata.py, services/billing-service/app/export_invoices.py, services/legacy-billing/app/finance_warehouse.py, services/admin-service/app/services/finance_warehouse/dashboard_queries.rb, services/analytics-service/src/main/scala/com/otterworks/analytics/finance/FinanceRollupRepository.scala, services/report-service/src/main/java/com/otterworks/report/financewarehouse/TeradataFinanceWarehouse.java

## A-200 — Deterministic latest version timestamp ties

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_DOCUMENTS.DOC_VERSION, bteq_script:warehouse/teradata/scripts/documents/02_current_versions.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/02_current_versions, teradata_view:SFX_DOCUMENTS.V_DOCUMENT_VERSIONS, teradata_view:SFX_DOCUMENTS.V_WORKSPACE_STORAGE

**ambiguity:** ROW_NUMBER orders only by VERSION_TS; equal timestamps do not define a winner.

**decision:** Approved policy: latest VERSION_TS, then highest VERSION_ID, retaining DESC NULLS FIRST ordering. Legacy QUALIFY ROW_NUMBER() OVER (PARTITION BY DOCUMENT_ID ORDER BY VERSION_TS DESC) = 1 has no contract for tied timestamps.

**rationale:** The fixture has 50 tied document groups; the emulator agrees with highest VERSION_ID in one and differs in 49. Approved candidate-set parity compares untied outputs exactly and tied winners against full latest-timestamp legacy staging rows. Workspace parity recomputes totals from legacy candidates selected by lakehouse version IDs and checks per-owner possible bounds, retaining exact published totals for untied owners. Reports expose exact-matched, tie-resolved and mismatch counts; no blanket normalization.

**verification:** documents.doc_version

**sources:** warehouse/teradata/scripts/documents/02_current_versions.bteq

## A-201 — Search history has no daily publisher

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_DOCUMENTS.SEARCH_INDEX_LOG, teradata_table:SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG, teradata_view:SFX_DOCUMENTS.V_SEARCH_HISTORY, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt

**ambiguity:** The loader populates STG_SEARCH_INDEX_LOG but the daily chain never copies it into SEARCH_INDEX_LOG.

**decision:** Keep staging populated; initialize SEARCH_INDEX_LOG empty and use an empty incremental append to preserve any existing target rows. Never publish staging implicitly.

**rationale:** Matches an untouched legacy table, not a repaired pipeline. External historical rows require an explicit initial migration, not this fresh fixture conversion.

**verification:** documents.search_index_log

**sources:** warehouse/teradata/jobs/daily_chain, warehouse/teradata/load/tpt/documents_search_index_log.tpt, warehouse/teradata/ddl/documents/00_tables.sql

## A-202 — Storage totals macro parameters and daily materialization

**status:** accepted

**risk:** low

**legacy_objects:** teradata_macro:SFX_DOCUMENTS.M_STORAGE_TOTALS

**ambiguity:** The legacy macro accepts arbitrary date boundaries; dbt tables are built for a business date.

**decision:** Expose documents_storage_totals(start_date, end_date) as a reusable SQL macro; materialize its current-business-month invocation in gold. Leave monthly billing writes and export to integration.

**rationale:** Preserves the half-open predicate and arbitrary SQL date arguments without claiming the shared monthly script.

**verification:** test:lakehouse/tests/test_documents.py::test_storage_set_and_macro_boundaries

**sources:** warehouse/teradata/macros/storage_totals.sql, warehouse/teradata/scripts/documents/10_storage_monthly.bteq

## A-203 — Documents staging width and target text conversion

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_DOCUMENTS.COLLAB_SESSION, bteq_script:warehouse/teradata/scripts/documents/05_load_sessions.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/05_load_sessions, teradata_table:SFX_DOCUMENTS.DOC_COMMENT, bteq_script:warehouse/teradata/scripts/documents/04_load_objects.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/04_load_objects, teradata_table:SFX_DOCUMENTS.DOC_SHARE, bteq_script:warehouse/teradata/scripts/documents/03_load_access.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/03_load_access, teradata_table:SFX_DOCUMENTS.DOC_TAG, teradata_table:SFX_DOCUMENTS.DOC_VERSION, bteq_script:warehouse/teradata/scripts/documents/02_current_versions.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/02_current_versions, teradata_table:SFX_DOCUMENTS.DOCUMENT, bteq_script:warehouse/teradata/scripts/documents/01_load_folders.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=documents/01_load_folders, teradata_table:SFX_DOCUMENTS.FILE_OBJECT, teradata_table:SFX_DOCUMENTS.FOLDER, teradata_table:SFX_DOCUMENTS.SEARCH_INDEX_LOG, teradata_table:SFX_DOCUMENTS.STG_COLLAB_SESSION, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_COMMENT, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_SHARE, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_TAG, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_VERSION, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, teradata_table:SFX_DOCUMENTS.STG_DOCUMENT, tpt:warehouse/teradata/load/tpt/documents_document.tpt, teradata_table:SFX_DOCUMENTS.STG_FILE_OBJECT, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, teradata_table:SFX_DOCUMENTS.STG_FOLDER, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, teradata_table:SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, teradata_table:SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt, teradata_table:SFX_DOCUMENTS.STORAGE_USAGE_DAILY

**ambiguity:** Spark string columns do not enforce Teradata VARCHAR or CHAR widths.

**decision:** Reject staging strings longer than 200; preserve null and empty strings. Apply foundation legacy_text truncation and fixed-width padding at publication, comparing CHAR columns with rstrip only.

**rationale:** Follows the executable emulator and foundation text contract; no case folding or whitespace trimming is introduced.

**verification:** test:lakehouse/tests/test_documents.py::test_document_text_and_load_failures

**sources:** warehouse/teradata/bteq/load.py, warehouse/teradata/ddl/documents/00_tables.sql, lakehouse/dbt/macros/legacy_text.sql

## A-204 — Parity staging keys describe the fixture rather than constraints

**status:** open

**risk:** med

**legacy_objects:** teradata_table:SFX_DOCUMENTS.STG_COLLAB_SESSION, tpt:warehouse/teradata/load/tpt/documents_collab_session.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_COMMENT, tpt:warehouse/teradata/load/tpt/documents_doc_comment.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_SHARE, tpt:warehouse/teradata/load/tpt/documents_doc_share.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_TAG, tpt:warehouse/teradata/load/tpt/documents_doc_tag.tpt, teradata_table:SFX_DOCUMENTS.STG_DOC_VERSION, tpt:warehouse/teradata/load/tpt/documents_doc_version.tpt, teradata_table:SFX_DOCUMENTS.STG_DOCUMENT, tpt:warehouse/teradata/load/tpt/documents_document.tpt, teradata_table:SFX_DOCUMENTS.STG_FILE_OBJECT, tpt:warehouse/teradata/load/tpt/documents_file_object.tpt, teradata_table:SFX_DOCUMENTS.STG_FOLDER, tpt:warehouse/teradata/load/tpt/documents_folder.tpt, teradata_table:SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG, tpt:warehouse/teradata/load/tpt/documents_search_index_log.tpt, teradata_table:SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY, tpt:warehouse/teradata/load/tpt/documents_storage_usage_daily.tpt

**ambiguity:** Legacy staging permits duplicate and null IDs while the parity engine requires unique non-null comparison keys.

**decision:** Use the generated feed identifiers for fresh fixture parity, without adding staging uniqueness or nullability constraints. Duplicate/null staging-key multiset parity remains unverified.

**rationale:** Do not tighten permissive legacy staging merely to satisfy a comparison tool.

**verification:** unverified: multiset parity for staging feeds containing duplicate or null identifiers requires a reader with occurrence keys

**sources:** warehouse/teradata/ddl/documents/00_tables.sql, lakehouse/parity/engine.py

## A-205 — Distinct stateful Informatica outputs and initial-state parity

**status:** accepted

**risk:** med

**legacy_objects:** informatica_mapping:SFX_CONTENT.m_SFX_STG_DOCUMENT, informatica_session:SFX_CONTENT.s_m_SFX_STG_DOCUMENT, informatica_source:SFX_CONTENT.FF_DOCUMENT, informatica_target:SFX_CONTENT.STG_DOCUMENT, informatica_mapping:SFX_CONTENT.m_SFX_DOCUMENT, informatica_session:SFX_CONTENT.s_m_SFX_DOCUMENT, informatica_source:SFX_CONTENT.STG_DOCUMENT, informatica_target:SFX_CONTENT.DOCUMENT, informatica_mapping:SFX_CONTENT.m_SFX_DOC_SHARE, informatica_session:SFX_CONTENT.s_m_SFX_DOC_SHARE, informatica_source:SFX_CONTENT.FF_DOC_SHARE, informatica_target:SFX_CONTENT.DOC_SHARE

**ambiguity:** The Informatica mappings differ from BTEQ snapshots and preserve prior target rows, cached insert/update decisions and per-session counts.

**decision:** Use a documents-only Python export node for PowerCenter port conversions and stateful writers. Persist independent infa_runtime_* Delta targets and diagnostics; publish four distinct dbt models through source(). Fresh parity starts both writers empty in an isolated legacy database, on the same landing files. Existing targets must be migrated before resuming a populated estate; do not bootstrap from BTEQ output implicitly. Atomically checkpoint the last input/code signature and full prepared batch before per-table Delta publication so retries restore the same rows and counters after a partial failure. A different date/input recomputes from existing targets; replays must be serialized.

**rationale:** The frozen DOCUMENT lookup distinguishes duplicate inserts from updates to existing keys; DOC_SHARE uses Update else Insert. Ordinary full snapshots would delete absent rows or conceal rejects. Session metrics prove row/reject counts, and unit tests cover updates, absent-row retention and duplicate keys. Replays must align target initial state before comparing action counts.

**verification:** test:lakehouse/tests/test_documents_informatica.py::test_retry_checkpoint_preserves_initial_counts_and_dates

**sources:** etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML, etl/informatica/runner/engine.py

## A-206 — Users bronze lookup fallback and explicit cross-domain readiness

**status:** accepted

**risk:** med

**legacy_objects:** informatica_mapping:SFX_CONTENT.m_SFX_DOCUMENT, informatica_session:SFX_CONTENT.s_m_SFX_DOCUMENT, informatica_source:SFX_CONTENT.STG_DOCUMENT, informatica_target:SFX_CONTENT.DOCUMENT, informatica_mapping:SFX_CONTENT.m_SFX_DOC_SHARE, informatica_session:SFX_CONTENT.s_m_SFX_DOC_SHARE, informatica_source:SFX_CONTENT.FF_DOC_SHARE, informatica_target:SFX_CONTENT.DOC_SHARE

**ambiguity:** No users silver model is present on this branch.

**decision:** Read business-date APP_USER and ROLE_GRANT from existing bronze_users sources. Add explicit bronze_users dependencies to the Informatica export and documents dbt task. Match any non-null owner status, including INACTIVE; do not introduce an ACTIVE-only predicate.

**rationale:** Implements the actual NOT ISNULL lookup filter while retaining users ownership. The legacy verification database copies the existing emulator user lookup tables produced from the same feeds.

**verification:** test:lakehouse/tests/test_documents_informatica.py::test_informatica_graph_dependencies_and_distinct_models

**sources:** etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOCUMENT.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOC_SHARE.XML

## A-207 — Unknown-owner filtering differs from rejected rows

**status:** accepted

**risk:** low

**legacy_objects:** informatica_mapping:SFX_CONTENT.m_SFX_DOCUMENT, informatica_session:SFX_CONTENT.s_m_SFX_DOCUMENT, informatica_source:SFX_CONTENT.STG_DOCUMENT, informatica_target:SFX_CONTENT.DOCUMENT

**ambiguity:** FIL_KNOWN_OWNER silently drops rows; it does not invoke DD_REJECT or write a bad file.

**decision:** Keep unknown/null-status owners out of DOCUMENT updates, retain existing target rows, and leave rejected counts unchanged. Persist filtered rows as an additional diagnostic. Expose transformation/writer rejection diagnostics separately and compare per-session rejected and transformation-error counts to the emulator.

**rationale:** Treating filtered owners as writer rejects would change legacy session counters. Actual writer rejects and transformation errors remain observable in Delta diagnostics and infa_metrics.

**verification:** test:lakehouse/tests/test_documents_informatica.py::test_owner_filter_is_not_reject_and_null_status_is_not_known

**sources:** etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOCUMENT.XML, etl/informatica/runner/engine.py

## A-208 — Lookup first-value policy has no ordering among duplicate user keys

**status:** open

**risk:** med

**legacy_objects:** informatica_mapping:SFX_CONTENT.m_SFX_DOCUMENT, informatica_session:SFX_CONTENT.s_m_SFX_DOCUMENT, informatica_source:SFX_CONTENT.STG_DOCUMENT, informatica_target:SFX_CONTENT.DOCUMENT, informatica_mapping:SFX_CONTENT.m_SFX_DOC_SHARE, informatica_session:SFX_CONTENT.s_m_SFX_DOC_SHARE, informatica_source:SFX_CONTENT.FF_DOC_SHARE, informatica_target:SFX_CONTENT.DOC_SHARE

**ambiguity:** The emulator orders lookup rows only by USER_ID and uses the first returned match; duplicate lookup keys have no secondary ordering.

**decision:** Use the first row delivered per lookup USER_ID, without inventing a role priority or secondary sort. Preserve case-sensitive ADMIN and EDITOR comparisons, CHAR rstrip and twelve-character lookup role ports. Shared fixture lookup keys are unique.

**rationale:** Fresh parity verifies unique-key lookups. Which physical duplicate wins across PostgreSQL and Spark remains unverified; operators must resolve duplicate lookup keys or approve candidate-set parity before claiming duplicate-key exact equivalence.

**verification:** test:lakehouse/tests/test_documents_informatica.py::test_empty_input_and_first_lookup_match

**sources:** etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOCUMENT.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOC_SHARE.XML, etl/informatica/runner/engine.py

## A-209 — PowerCenter file ports and distinct staging multiset comparison

**status:** accepted

**risk:** med

**legacy_objects:** informatica_mapping:SFX_CONTENT.m_SFX_STG_DOCUMENT, informatica_session:SFX_CONTENT.s_m_SFX_STG_DOCUMENT, informatica_source:SFX_CONTENT.FF_DOCUMENT, informatica_target:SFX_CONTENT.STG_DOCUMENT, informatica_mapping:SFX_CONTENT.m_SFX_DOC_SHARE, informatica_session:SFX_CONTENT.s_m_SFX_DOC_SHARE, informatica_source:SFX_CONTENT.FF_DOC_SHARE, informatica_target:SFX_CONTENT.DOC_SHARE

**ambiguity:** PowerCenter source ports truncate strings before expressions and use QUOTE_NONE, unlike the BTEQ loader.

**decision:** Read the same landing files with PowerCenter blank/null, quoting and missing-field behavior. Apply qualifier widths, numeric-prefix truncating casts, space-only trims, uppercase and strict date ports before writing. Preserve staging duplicates/null keys and compare full-row occurrence-numbered multisets; compare typed legacy PostgreSQL outputs directly so null and empty text remain distinct.

**rationale:** A BTEQ staging snapshot is not evidence for these source transformations. Target CHAR parity uses rstrip only; malformed transformations and target overflow/null-key failures remain counted rather than silently coerced.

**verification:** test:lakehouse/tests/test_documents_informatica.py::test_ports_match_legacy_expression_and_qualifier_widths

**sources:** etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_STG_DOCUMENT.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOC_SHARE.XML, etl/informatica/runner/engine.py, etl/informatica/runner/expr.py

## A-210 — Spark-specific dated shared feeds

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:docs_storage_by_owner, spark_submit:etl/spark/submit/docs_storage_by_owner.sh, cron_entry:etl/crontab#6cccad9ba92f, spark_job:docs_share_activity, spark_submit:etl/spark/submit/docs_share_activity.sh, cron_entry:etl/crontab#e913aaa5c3d7, spark_job:docs_folder_legacy_report, spark_submit:etl/spark/submit/docs_folder_legacy_report.sh, cron_entry:etl/crontab#b40205d7056e, spark_job:docs_search_log_parse, spark_submit:etl/spark/submit/docs_search_log_parse.sh, cron_entry:etl/crontab#0994e1d7781b, spark_job:docs_tag_normalize, spark_submit:etl/spark/submit/docs_tag_normalize.sh, cron_entry:etl/crontab#7ce72803f1b1, spark_job:docs_event_export_hourly, spark_submit:etl/spark/submit/docs_event_export_hourly.sh, cron_entry:etl/crontab#06b1c260f55b, spark_job:lake_compaction_documents, spark_submit:etl/spark/submit/lake_compaction_documents.sh, cron_entry:etl/crontab#d379dc30b522

**ambiguity:** Spark feed layouts are not the Teradata or Informatica layouts; Scala infers CSV types while Python supplies nullable schemas.

**decision:** Read the identical immutable spark/{business_date} files on both sides. Preserve explicit Python schemas, permissive cell casts, Scala inference, Unicode Python regex/normalization, null sums and duplicate counts; fail fast on absent feeds, changed manifests or malformed headers.

**rationale:** The dated generator and per-file SHA-256 manifest make the fixture independently reproducible. The legacy sources and both Scala classes run unchanged; their common libraries remain integration-owned.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_spark_feed_transforms_normal

**sources:** etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/common/runtime.py, etl/spark/scala/src/main/scala/sfx/BatchSupport.scala, lakehouse/parity/documents_spark_fixture.py

## A-211 — Disabled folder-report cron remains disabled

**status:** accepted

**risk:** low

**legacy_objects:** spark_job:docs_folder_legacy_report, spark_submit:etl/spark/submit/docs_folder_legacy_report.sh, cron_entry:etl/crontab#b40205d7056e

**ambiguity:** The folder report is implemented but its legacy cron is commented out.

**decision:** Provide a paused, unscheduled manual-only folder-report DAG and distinct output/parity spec. Do not add it to an active daily DAG.

**rationale:** Converting logic must not reactivate a disabled report.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_documents_spark_cron_replacements

**sources:** etl/crontab, etl/spark/jobs/py/docs_folder_legacy_report.py

## A-212 — Hourly document export cadence and bucket contract

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:docs_event_export_hourly, spark_submit:etl/spark/submit/docs_event_export_hourly.sh, cron_entry:etl/crontab#06b1c260f55b

**ambiguity:** The foundation hourly DAG was a paused stub; legacy exports at minute 18 and partitions by Spark pmod(DOCUMENT_ID, 10000).

**decision:** Replace the stub with the real export, dbt output and parity tasks. Keep schedule 18 * * * * and paused=true. Retain UTC logical-business-date handling, eight-way bucket repartitioning, overwrite snapshot semantics and nonnegative pmod buckets even for negative IDs.

**rationale:** An unchanged input snapshot produces identical rows and bucket membership on retries; no append or new active hourly schedule is introduced.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_documents_spark_cron_replacements

**sources:** etl/crontab, etl/spark/jobs/py/docs_event_export_hourly.py, lakehouse/orchestration/pipeline.yaml

## A-213 — Atomic snapshot publication on the local filesystem

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:docs_event_export_hourly, spark_submit:etl/spark/submit/docs_event_export_hourly.sh, cron_entry:etl/crontab#06b1c260f55b, spark_job:lake_compaction_documents, spark_submit:etl/spark/submit/lake_compaction_documents.sh, cron_entry:etl/crontab#d379dc30b522

**ambiguity:** Legacy directory overwrite exposes partial output; compaction must not switch snapshots while reading.

**decision:** Write a unique immutable version, require _SUCCESS and unchanged input hashes, then atomically replace a symlink. Pin resolved paths before Parquet reads, retain prior versions, and compact with coalesce(4). Idempotency is logical row/bucket equality, not stable filenames or identical version UUIDs.

**rationale:** POSIX rename provides all-or-old publication on this single host; a failed write, validation or pointer swap retains the previous snapshot. Distributed/object-store publication and garbage collection are not implemented.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_atomic_idempotent_partition_publication_and_pinned_reader

**sources:** etl/spark/jobs/py/docs_event_export_hourly.py, etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala, lakehouse/runtime/documents_spark.py

## A-214 — Compaction retains 02:19 cadence behind paused export

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:lake_compaction_documents, spark_submit:etl/spark/submit/lake_compaction_documents.sh, cron_entry:etl/crontab#d379dc30b522

**ambiguity:** Compaction is daily at 02:19, not hourly, but its converted producer intentionally remains paused.

**decision:** Use a separate 19 2 * * * DAG, initially paused alongside the hourly producer. A date-scoped readiness task waits for a committed hourly snapshot before compaction; resolve and pin that version. Enable only when the export is explicitly enabled.

**rationale:** Running compaction hourly would silently change the cron contract; activating a consumer while its producer is paused would cause avoidable timeouts.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_documents_spark_cron_replacements

**sources:** etl/crontab, etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala, lakehouse/orchestration/pipeline.yaml

## A-215 — Independent Spark dbt outputs and exact cron replacements

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:docs_storage_by_owner, spark_submit:etl/spark/submit/docs_storage_by_owner.sh, cron_entry:etl/crontab#6cccad9ba92f, spark_job:docs_share_activity, spark_submit:etl/spark/submit/docs_share_activity.sh, cron_entry:etl/crontab#e913aaa5c3d7, spark_job:docs_folder_legacy_report, spark_submit:etl/spark/submit/docs_folder_legacy_report.sh, cron_entry:etl/crontab#b40205d7056e, spark_job:docs_search_log_parse, spark_submit:etl/spark/submit/docs_search_log_parse.sh, cron_entry:etl/crontab#0994e1d7781b, spark_job:docs_tag_normalize, spark_submit:etl/spark/submit/docs_tag_normalize.sh, cron_entry:etl/crontab#7ce72803f1b1, spark_job:docs_event_export_hourly, spark_submit:etl/spark/submit/docs_event_export_hourly.sh, cron_entry:etl/crontab#06b1c260f55b, spark_job:lake_compaction_documents, spark_submit:etl/spark/submit/lake_compaction_documents.sh, cron_entry:etl/crontab#d379dc30b522

**ambiguity:** The existing documents bronze feeds have incompatible columns; paused/manual Spark sources cannot be prerequisites of the active BTEQ dbt build.

**decision:** Keep native dated Spark feeds isolated from warehouse bronze, expose date-partitioned Spark runtime Delta sources and seven distinct silver dbt models. Enable a model only for DOCUMENTS_SPARK_JOB=<job> (or all for explicit validation). Each job DAG selects its model, tests and parity; four enabled daily cron replacements keep their original UTC minute/hour and explicit Spark feed sensors, including users APP_USER.

**rationale:** This follows the independent runtime-source pattern used for Informatica and prevents a tag:documents build from implicitly executing paused or disabled schedules. Source metadata is declared without claiming ownership of shared schemas or the users pipeline.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_documents_spark_cron_replacements

**sources:** etl/crontab, lakehouse/dbt/models/sources.yml, lakehouse/orchestration/pipeline.yaml, lakehouse/dbt/models/silver/documents/spark_docs_storage_by_owner.sql

## A-216 — Empty partitioned exports do not supply an inferred Parquet schema

**status:** accepted

**risk:** low

**legacy_objects:** spark_job:docs_event_export_hourly, spark_submit:etl/spark/submit/docs_event_export_hourly.sh, cron_entry:etl/crontab#06b1c260f55b, spark_job:lake_compaction_documents, spark_submit:etl/spark/submit/lake_compaction_documents.sh, cron_entry:etl/crontab#d379dc30b522

**ambiguity:** Spark writes an empty partitioned export with _SUCCESS but no data files; the unmodified Scala compactor cannot infer its schema.

**decision:** Publish the empty export successfully and preserve its schema for the dbt runtime table. Preserve the legacy compactor's failure on a completely empty partitioned source rather than invent rows or silently treat missing input as empty.

**rationale:** Readiness proves a completed publication, not a nonempty data set. Unit tests distinguish missing feeds, header-only feeds, empty transforms, successful empty publication and the missing-inference compaction error.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_atomic_idempotent_partition_publication_and_pinned_reader

**sources:** etl/spark/jobs/py/docs_event_export_hourly.py, etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala

## A-217 — Fixed twenty-step folder walking, including cycles and zero parents

**status:** accepted

**risk:** low

**legacy_objects:** spark_job:docs_folder_tree_walk, spark_submit:etl/spark/submit/docs_folder_tree_walk.sh, cron_entry:etl/crontab#5c3511fa77a1

**ambiguity:** The legacy parent walk has a fixed iteration budget, not a root-convergence condition.

**decision:** Run exactly twenty transitions. Deep trees truncate at their twentieth ancestor; cycles continue to depth twenty. Preserve parent-or-current behavior for zero parents, dangling parents and null roots.

**rationale:** Avoid repairing the legacy graph or introducing cycle detection that changes output.

**verification:** documents.spark_docs_folder_tree_walk

**sources:** etl/spark/jobs/py/docs_folder_tree_walk.py

## A-218 — Seeded four-hop directed share reachability

**status:** accepted

**risk:** low

**legacy_objects:** spark_job:doc_share_graph_reach, spark_submit:etl/spark/submit/doc_share_graph_reach.sh, cron_entry:etl/crontab#817f451e90ab

**ambiguity:** Duplicate edges, self shares, cycles and disconnected components are present.

**decision:** Start with user 1 at distance zero even for empty shares; traverse directed owner-to-recipient edges for at most four hops, deduplicate visited users and retain minimum distance.

**rationale:** The legacy job does not filter via DOCUMENT or interpret permissions. The fixture includes a fifth-hop node that must remain absent.

**verification:** documents.spark_doc_share_graph_reach

**sources:** etl/spark/jobs/py/doc_share_graph_reach.py

## A-219 — Collaboration sessions use a strict greater-than gap

**status:** accepted

**risk:** low

**legacy_objects:** spark_job:collab_session_sessionize, spark_submit:etl/spark/submit/collab_session_sessionize.sh, cron_entry:etl/crontab#afa009bc6185

**ambiguity:** SESSION_ID is present in the feed but is not the legacy grouping key.

**decision:** Group by user and document, sort event timestamps, split only when the adjacent gap exceeds 1800 seconds, number sessions from one. Keep duplicate timestamps; exactly 1800 seconds remains in the current session.

**rationale:** The fixture exercises unsorted events, duplicate times, exact boundary and 1801-second gaps. Mixed null/non-null timestamps retain Python sort failure, not invented event times.

**verification:** documents.spark_collab_session_sessionize

**sources:** etl/spark/jobs/py/collab_session_sessionize.py

## A-220 — Exact Python SequenceMatcher similarity

**status:** accepted

**risk:** low

**legacy_objects:** spark_job:doc_version_diff_stats, spark_submit:etl/spark/submit/doc_version_diff_stats.sh, cron_entry:etl/crontab#d54b23093fd1

**ambiguity:** Similarity is order-sensitive and long repeated bodies engage SequenceMatcher default autojunk behavior.

**decision:** Use difflib.SequenceMatcher(None, before or empty string, after or empty string).ratio(), preserving default autojunk and ascending VERSION_NUMBER lag. Compare doubles exactly: no scale rounding, epsilon or float tolerance.

**rationale:** Both sides execute the same Python runtime and standard-library algorithm; full-row exact parity must demonstrate that tolerance is unnecessary.

**verification:** documents.spark_doc_version_diff_stats

**sources:** etl/spark/jobs/py/doc_version_diff_stats.py

## A-221 — Binary extraction errors, estimates and zero-byte omission

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:file_object_binary_extract, spark_submit:etl/spark/submit/file_object_binary_extract.sh, cron_entry:etl/crontab#9f970c1cb2a8, spark_library:etl/spark/jobs/py/common/binary_documents.py

**ambiguity:** Binary extraction is a lightweight legacy parser rather than a general PDF/Office renderer; Spark omits zero-length file rows.

**decision:** Preserve signature/ZIP detection, DOCX XML text parsing, text truncation at 4096 characters, page estimates before truncation, raw SHA256 and bounded error strings. Reject DTDs/entities. Keep inner metadata/blob join, duplicate blob references and unmatched-file omission. A zero-byte file is in inputFiles and the manifest but yields no binaryFile row; direct empty-byte library extraction still returns the legacy error tuple.

**rationale:** The shared fixture contains valid PDF/DOCX/ZIP, long text, malformed PDF/ZIP/XML, DTD XML, unsupported and zero-byte blobs. The unchanged job reports twelve input files, 7298 bytes and eleven joined output rows. Corrupt nonempty blobs retain error rows.

**verification:** documents.spark_file_object_binary_extract

**sources:** etl/spark/jobs/py/file_object_binary_extract.py, etl/spark/jobs/py/common/binary_documents.py

## A-222 — Duplicate folder keys and version-order ties remain unspecified

**status:** open

**risk:** med

**legacy_objects:** spark_job:docs_folder_tree_walk, spark_submit:etl/spark/submit/docs_folder_tree_walk.sh, cron_entry:etl/crontab#5c3511fa77a1, spark_job:doc_version_diff_stats, spark_submit:etl/spark/submit/doc_version_diff_stats.sh, cron_entry:etl/crontab#d54b23093fd1

**ambiguity:** Legacy folder collect-to-dict and VERSION_NUMBER-only lag do not define winners for duplicate keys or tied ordering values.

**decision:** Preserve those operators without inventing a tie policy. Parity fixture folder IDs and per-document VERSION_NUMBER values are unique. Populated inputs with duplicate folder IDs or version-number ties require a reviewed equivalence policy before production migration.

**rationale:** Unlike the separately approved Teradata VERSION_TS policy, no Spark tie decision was requested; the fixture cannot establish ordering guarantees for tied rows.

**verification:** documents.spark_docs_folder_tree_walk

**sources:** etl/spark/jobs/py/docs_folder_tree_walk.py, etl/spark/jobs/py/doc_version_diff_stats.py

## A-223 — Isolated dated second-batch feeds and exact cron replacements

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:docs_folder_tree_walk, spark_submit:etl/spark/submit/docs_folder_tree_walk.sh, cron_entry:etl/crontab#5c3511fa77a1, spark_job:doc_share_graph_reach, spark_submit:etl/spark/submit/doc_share_graph_reach.sh, cron_entry:etl/crontab#817f451e90ab, spark_job:collab_session_sessionize, spark_submit:etl/spark/submit/collab_session_sessionize.sh, cron_entry:etl/crontab#afa009bc6185, spark_job:doc_version_diff_stats, spark_submit:etl/spark/submit/doc_version_diff_stats.sh, cron_entry:etl/crontab#d54b23093fd1, spark_job:file_object_binary_extract, spark_submit:etl/spark/submit/file_object_binary_extract.sh, cron_entry:etl/crontab#9f970c1cb2a8, spark_library:etl/spark/jobs/py/common/binary_documents.py

**ambiguity:** Extending the first fixture in place would invalidate recorded shared-input provenance.

**decision:** Use warehouse/landing/documents-second/spark/<business_date> for both engines, with hashes for every CSV and blob. Preserve original UTC 03:21, 03:23, 03:24, 03:25 and 03:26 schedules in dedicated DAGs. CSV readiness gates execution; the runtime manifest validates the complete requested blob/CSV set before work and again before publication.

**rationale:** This keeps first-batch feeds/evidence intact and retains native Spark schemas rather than warehouse snapshots. Blob files are written before the manifest; incomplete or changed manifests fail safely and retry.

**verification:** test:lakehouse/tests/test_documents_spark.py::test_documents_spark_second_cron_replacements

**sources:** etl/spark/jobs/py/docs_folder_tree_walk.py, etl/spark/jobs/py/doc_share_graph_reach.py, etl/spark/jobs/py/collab_session_sessionize.py, etl/spark/jobs/py/doc_version_diff_stats.py, etl/spark/jobs/py/file_object_binary_extract.py, etl/crontab

## A-224 — External maintenance schedules remain paused

**status:** accepted

**risk:** high

**legacy_objects:** etl_script:etl/scripts/search_reindex_weekly.py, cron_entry:etl/crontab#69562b8e166b, etl_script:etl/scripts/storage_cleanup_daily.py, cron_entry:etl/crontab#fd7befdb4e7d

**ambiguity:** Legacy cron jobs target real services and cloud storage; enabling a translated schedule could mutate production.

**decision:** Keep Sunday 04:00 search and daily 02:30 cleanup schedules in UTC, initially paused. Retain zero task retries, matching cron rather than adding automatic replay of partial destructive work. Keep fake verification in a separate paused manual-only DAG.

**rationale:** Explicit operator review of endpoints, credentials and catchup is required before unpausing. No real external system was contacted for parity.

**verification:** test:lakehouse/tests/test_documents_external.py::test_documents_external_cron_replacements

**sources:** etl/crontab, lakehouse/orchestration/pipeline.yaml

## A-225 — Cleanup has no dry-run and preserves partial quarantine failures

**status:** accepted

**risk:** high

**legacy_objects:** etl_script:etl/scripts/storage_cleanup_daily.py, cron_entry:etl/crontab#fd7befdb4e7d

**ambiguity:** The legacy TODO says dry-run was never implemented; the cleanup report counts orphan bytes even when moves fail.

**decision:** Do not invent or honor a dry-run flag. Validate the twelve-digit bucket owner before creating AWS clients; preserve owner arguments on copy, delete and report put, and preserve their absence on listing. Copy each orphan first; delete only after copy returns. Continue after copy/delete failures, count failed moves, and calculate savings from all discovered orphan bytes as legacy does.

**rationale:** A successful copy followed by a failed delete leaves both source and quarantine objects and counts as failed. Preserve the exact report rather than claiming successful freed storage. Fake failure scenarios prove the action ordering and owner guards.

**verification:** documents.external_cleanup_actions

**sources:** etl/scripts/storage_cleanup_daily.py, etl/scripts/bucket_owner.py

## A-226 — Search retains polling and count-validation quirks

**status:** accepted

**risk:** med

**legacy_objects:** etl_script:etl/scripts/search_reindex_weekly.py, cron_entry:etl/crontab#69562b8e166b

**ambiguity:** The legacy script ignores delete exceptions, tolerates failed/timed-out asynchronous tasks, and does not use its declared 500-row bulk size.

**decision:** Keep 100-row API pages and one indexed batch per page; preserve documents/items and files/items fallbacks, explicit nulls, field defaults, settings and both final count checks. Poll 60 seconds for delete/create/settings and 120 seconds for index submissions. Failed or expired tasks do not independently abort; RPC failures outside delete do. Missing/blank required API keys abort before any request.

**rationale:** Hardening retries, HTTP timeouts or task-state failure policy would change the requested legacy contract. Tests compare emitted indexes and ordered requests, including no-taskUid, queued, failed, timeout and count-error scenarios.

**verification:** documents.external_search_actions

**sources:** etl/scripts/search_reindex_weekly.py, etl/scripts/runtime_config.py

## A-227 — External jobs retain wall-clock live-state semantics

**status:** accepted

**risk:** high

**legacy_objects:** etl_script:etl/scripts/search_reindex_weekly.py, cron_entry:etl/crontab#69562b8e166b, etl_script:etl/scripts/storage_cleanup_daily.py, cron_entry:etl/crontab#fd7befdb4e7d

**ambiguity:** Legacy scripts read current external state; cleanup report dates and quarantine keys use UTC wall time, not a historical business-date feed.

**decision:** Business date scopes local evidence and Airflow task labels only. Preserve current-state service reads and UTC execution-time cleanup keys/generated_at. Freeze the same injected clock in both parity engines and compare timestamps without normalization. Local run receipts use atomic replacement, but external index rebuilds and copy/delete/report sequences remain nontransactional.

**rationale:** Backfilling a paused DAG must not be presented as historical external-state replay. Rerunning search clears/rebuilds indexes; rerunning cleanup relists changed state and may overwrite the current-day report. Operators must review catchup and partial side effects before activation.

**verification:** documents.external_cleanup_report

**sources:** etl/scripts/search_reindex_weekly.py, etl/scripts/storage_cleanup_daily.py, lakehouse/runtime/documents_external.py

## A-228 — External parity uses injected service contracts, not real infrastructure

**status:** accepted

**risk:** med

**legacy_objects:** etl_script:etl/scripts/search_reindex_weekly.py, cron_entry:etl/crontab#69562b8e166b, etl_script:etl/scripts/storage_cleanup_daily.py, cron_entry:etl/crontab#fd7befdb4e7d

**ambiguity:** Live service credentials and real destructive operations are not appropriate for conversion verification.

**decision:** Execute unchanged legacy script main functions and the native task functions with fresh strict in-memory HTTP/S3/DynamoDB clients built from the same dated JSON fixture. Inject identical clocks, config and fixture-only credentials. Compare full index/settings states, serialized report bytes, final object states, ordered requests/actions and outcomes across thirteen search and nine cleanup scenarios.

**rationale:** Source and fixture hashes record the exact oracle and conversion used. Unknown HTTP endpoints fail locally; no client attempts network I/O. This establishes contract parity against fakes, not MeiliSearch async visibility, real IAM, cloud consistency or SDK wire-level behavior.

**verification:** test:lakehouse/tests/test_documents_external.py::test_unchanged_legacy_external_scenarios

**sources:** etl/scripts/search_reindex_weekly.py, etl/scripts/storage_cleanup_daily.py, lakehouse/parity/documents_external.py, lakehouse/parity/documents_external_fakes.py

## A-229 — External task client dependencies are explicit

**status:** accepted

**risk:** med

**legacy_objects:** etl_script:etl/scripts/search_reindex_weekly.py, cron_entry:etl/crontab#69562b8e166b, etl_script:etl/scripts/storage_cleanup_daily.py, cron_entry:etl/crontab#fd7befdb4e7d

**ambiguity:** The lakehouse environment previously had requests only transitively and no boto3, so a native cleanup task could not create AWS clients.

**decision:** Declare pinned requests and boto3 in lakehouse requirements. Keep client objects injectable into task functions and retain the existing ETL_CONFIG_PATH, required API key and bucket-owner environment interfaces. Do not claim ownership or alter legacy shared runtime_config/bucket_owner helpers.

**rationale:** This dependency-file change is necessary for the two native tasks, not a shared integration conversion. Fake parity proves client call contracts; live endpoint deployment and SDK transport behavior remain unverified.

**verification:** test:lakehouse/tests/test_documents_external.py::test_external_task_entrypoint_injected_clients

**sources:** lakehouse/requirements.txt, etl/requirements.txt, etl/scripts/runtime_config.py, etl/scripts/bucket_owner.py

## A-300 — Warehouse snapshots and state

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_USERS.APP_USER, teradata_table:SFX_USERS.LOGIN_EVENT, teradata_table:SFX_USERS.ROLE_GRANT, teradata_table:SFX_USERS.SSO_IDENTITY, teradata_table:SFX_USERS.TEAM, teradata_table:SFX_USERS.TEAM_MEMBER, teradata_table:SFX_USERS.USER_ACTIVITY_DAILY, teradata_table:SFX_USERS.USER_PROFILE, teradata_table:SFX_USERS.USER_STATUS_HIST

**ambiguity:** Do repeated dates accumulate or overwrite working tables?

**decision:** Filter to the requested bronze partition; rebuild final snapshots like the date chain. Keep older inputs in bronze, not final snapshots.

**rationale:** Legacy BTEQ deletes the final tables before each reload.

**verification:** users.app_user

**sources:** warehouse/teradata/ddl/users/00_tables.sql

## A-301 — Warehouse string types and case

**status:** accepted

**risk:** med

**legacy_objects:** teradata_table:SFX_USERS.APP_USER, teradata_table:SFX_USERS.LOGIN_EVENT, teradata_table:SFX_USERS.ROLE_GRANT, teradata_table:SFX_USERS.SSO_IDENTITY, teradata_table:SFX_USERS.TEAM, teradata_table:SFX_USERS.TEAM_MEMBER, teradata_table:SFX_USERS.USER_ACTIVITY_DAILY, teradata_table:SFX_USERS.USER_PROFILE, teradata_table:SFX_USERS.USER_STATUS_HIST

**ambiguity:** Teradata and the emulator differ in CHAR padding and native truncation.

**decision:** Cast SQL types, apply legacy CHAR widths and UPPER only where applicable, compare fixed-width values without trailing ASCII spaces.

**rationale:** Only fixed-width padding is normalized; variable-width data is preserved.

**verification:** users.app_user

**sources:** warehouse/teradata/ddl/users/00_tables.sql

## A-302 — Unloaded warehouse preference target

**status:** open

**risk:** high

**legacy_objects:** fastload:warehouse/teradata/load/fastload/users_user_pref.fl, teradata_table:SFX_USERS.STG_USER_PREF, teradata_table:SFX_USERS.USER_PREF, teradata_view:SFX_USERS.V_USER_SETTINGS

**ambiguity:** FastLoad stages preferences but no users BTEQ INSERT populates USER_PREF.

**decision:** Expose a schema-correct empty warehouse snapshot and settings view; keep loaded STG_USER_PREF and the independent Spark JSON outputs.

**rationale:** Avoid fabricating a warehouse promotion rule; equality of empty finals does not verify a future load.

**verification:** users.stg_user_pref

**sources:** warehouse/teradata/ddl/users/00_tables.sql, warehouse/teradata/ddl/users/10_views.sql, warehouse/teradata/load/fastload/users_user_pref.fl

## A-303 — Derived activity identifier reservation

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/users/10_activity_daily.bteq, teradata_procedure:SFX_USERS.P_ACTIVITY_DAILY, teradata_table:SFX_USERS.USER_ACTIVITY_DAILY

**ambiguity:** The procedure deletes IDs at or above ten billion, then reports an OUT count.

**decision:** Reserve that range, count all logins for the requested date, set document_count to zero, and compare persisted rows without exposing a procedure-style OUT parameter.

**rationale:** The BTEQ call has no downstream dependency on the OUT value.

**verification:** users.user_activity_daily

**sources:** warehouse/teradata/ddl/users/00_tables.sql, warehouse/teradata/procedures/activity_daily.sql, warehouse/teradata/scripts/users/10_activity_daily.bteq

## A-304 — View comparison retains duplicates

**status:** accepted

**risk:** low

**legacy_objects:** teradata_view:SFX_USERS.V_TEAM_MEMBERS, teradata_view:SFX_USERS.V_USER_SETTINGS

**ambiguity:** Views expose no unique occurrence ID and repeat tuples for duplicate links.

**decision:** Assign a deterministic occurrence for comparison only, sorted by the full tuple using explicit null ordering and binary collation.

**rationale:** This preserves bag multiplicity without adding columns to consumers.

**verification:** users.v_team_members

**sources:** warehouse/teradata/ddl/users/10_views.sql

## A-305 — Team count extract order and date

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/users/10_activity_daily.bteq, teradata_macro:SFX_USERS.M_TEAM_COUNTS

**ambiguity:** The macro accepts an unused day argument, has no ORDER BY, and the emulator writes an undated file.

**decision:** Rebuild the macro against the requested warehouse snapshot, emit a sorted, date-scoped PSV, and compare rows keyed by team ID to the legacy BTEQ file generated for that date.

**rationale:** The data is unchanged; order becomes deterministic and the oracle file must come from the matching run.

**verification:** users.team_counts

**sources:** warehouse/teradata/macros/team_counts.sql, warehouse/teradata/scripts/users/10_activity_daily.bteq

## A-306 — Informatica and BTEQ writer separation

**status:** open

**risk:** high

**legacy_objects:** informatica_mapping:SFX_CONTENT.m_SFX_APP_USER, informatica_mapping:SFX_CONTENT.m_SFX_LOGIN_EVENT, informatica_mapping:SFX_CONTENT.m_SFX_ROLE_GRANT, informatica_mapping:SFX_CONTENT.m_SFX_STG_APP_USER, informatica_mapping:SFX_CONTENT.m_SFX_TEAM_MEMBER, informatica_session:SFX_CONTENT.s_m_SFX_APP_USER, informatica_session:SFX_CONTENT.s_m_SFX_LOGIN_EVENT, informatica_session:SFX_CONTENT.s_m_SFX_ROLE_GRANT, informatica_session:SFX_CONTENT.s_m_SFX_STG_APP_USER, informatica_session:SFX_CONTENT.s_m_SFX_TEAM_MEMBER, informatica_source:SFX_CONTENT.FF_APP_USER, informatica_source:SFX_CONTENT.FF_LOGIN_EVENT, informatica_source:SFX_CONTENT.FF_ROLE_GRANT, informatica_source:SFX_CONTENT.FF_TEAM_MEMBER, informatica_source:SFX_CONTENT.STG_APP_USER, informatica_target:SFX_CONTENT.APP_USER, informatica_target:SFX_CONTENT.LOGIN_EVENT, informatica_target:SFX_CONTENT.ROLE_GRANT, informatica_target:SFX_CONTENT.STG_APP_USER, informatica_target:SFX_CONTENT.TEAM_MEMBER

**ambiguity:** Both paths write overlapping table names, but one normalizes/upserts where the other reloads.

**decision:** Keep distinct silver targets and a separate legacy oracle database; integration must choose cutover ownership where two writers target the same logical entity.

**rationale:** Fixture equivalence in each path does not establish precedence or safe dual writes.

**verification:** users.infa_app_user

**sources:** etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_APP_USER.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_LOGIN_EVENT.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_ROLE_GRANT.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_STG_APP_USER.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_TEAM_MEMBER.XML, etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML

## A-307 — Informatica update and lookup keys

**status:** open

**risk:** high

**legacy_objects:** informatica_mapping:SFX_CONTENT.m_SFX_APP_USER, informatica_mapping:SFX_CONTENT.m_SFX_LOGIN_EVENT, informatica_mapping:SFX_CONTENT.m_SFX_ROLE_GRANT, informatica_mapping:SFX_CONTENT.m_SFX_STG_APP_USER, informatica_mapping:SFX_CONTENT.m_SFX_TEAM_MEMBER, informatica_session:SFX_CONTENT.s_m_SFX_APP_USER, informatica_session:SFX_CONTENT.s_m_SFX_LOGIN_EVENT, informatica_session:SFX_CONTENT.s_m_SFX_ROLE_GRANT, informatica_session:SFX_CONTENT.s_m_SFX_STG_APP_USER, informatica_session:SFX_CONTENT.s_m_SFX_TEAM_MEMBER, informatica_source:SFX_CONTENT.FF_APP_USER, informatica_source:SFX_CONTENT.FF_LOGIN_EVENT, informatica_source:SFX_CONTENT.FF_ROLE_GRANT, informatica_source:SFX_CONTENT.FF_TEAM_MEMBER, informatica_source:SFX_CONTENT.STG_APP_USER, informatica_target:SFX_CONTENT.APP_USER, informatica_target:SFX_CONTENT.LOGIN_EVENT, informatica_target:SFX_CONTENT.ROLE_GRANT, informatica_target:SFX_CONTENT.STG_APP_USER, informatica_target:SFX_CONTENT.TEAM_MEMBER

**ambiguity:** PowerCenter update strategy, reject handling, and post-session state are not relational query outputs.

**decision:** Preserve truncate versus merge and classify login outcomes. Use non-null unique merge keys; fail a batch rather than publishing partial DTM rejects. Run new dates in order against matching state.

**rationale:** Delta transactions prevent ambiguous duplicate updates; row counts alone do not prove production reject thresholds or replay semantics.

**verification:** test:lakehouse/tests/test_users.py::test_informatica_delta_contract

**sources:** etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_APP_USER.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_LOGIN_EVENT.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_ROLE_GRANT.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_STG_APP_USER.XML, etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_TEAM_MEMBER.XML, etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML

## A-308 — Spark input and publication contracts

**status:** open

**risk:** high

**legacy_objects:** spark_job:team_graph_components, spark_job:user_pref_json_flatten, spark_job:users_active_daily, spark_job:users_login_useragent_parse, spark_job:users_risk_score, spark_job:users_team_rollup, spark_submit:etl/spark/submit/team_graph_components.sh, spark_submit:etl/spark/submit/user_pref_json_flatten.sh, spark_submit:etl/spark/submit/users_active_daily.sh, spark_submit:etl/spark/submit/users_login_useragent_parse.sh, spark_submit:etl/spark/submit/users_risk_score.sh, spark_submit:etl/spark/submit/users_team_rollup.sh

**ambiguity:** Spark and warehouse feeds use different columns, dates and source widths; some Spark jobs dual-write.

**decision:** Stage a separate business-day Spark landing bundle with the same per-file schemas. Gold overwrites the current snapshot; both JDBC copies compare to their common Delta output.

**rationale:** This eliminates duplicate writes in the demo. Real JDBC readers require a catalog cutover, and out-of-order historical snapshots must use a separate namespace.

**verification:** users.users_team_rollup_jdbc

**sources:** etl/spark/jobs.txt, etl/spark/submit/team_graph_components.sh, etl/spark/submit/user_pref_json_flatten.sh, etl/spark/submit/users_active_daily.sh, etl/spark/submit/users_login_useragent_parse.sh, etl/spark/submit/users_risk_score.sh, etl/spark/submit/users_team_rollup.sh

## A-309 — Scala risk model numeric boundary

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:users_risk_score

**ambiguity:** Legacy Spark passes a LONG count into an Int Scala UDF and uses Java floating arithmetic.

**decision:** Emulate signed Int narrowing and compare only risk_score with absolute tolerance 1e-14.

**rationale:** Integer inputs and identities still require exact equality; only JVM arithmetic is tolerant.

**verification:** users.users_risk_score

**sources:** etl/spark/jobs.txt

## A-310 — Graph components and malformed input

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:team_graph_components

**ambiguity:** Duplicate membership edges and orphan team IDs coexist in the source graph.

**decision:** Take the minimum team ID through shared users until convergence, retain isolated and membership-only teams, reject null identifiers.

**rationale:** This avoids materializing all team pairs while preserving the legacy result and failure for null IDs.

**verification:** test:lakehouse/tests/test_users.py::test_users_spark_edges

**sources:** etl/spark/jobs.txt

## A-311 — Browser and JSON boundary

**status:** accepted

**risk:** low

**legacy_objects:** spark_job:users_login_useragent_parse, spark_job:user_pref_json_flatten

**ambiguity:** Legacy user-agent parsing returns the first browser token; JSON flattening stringifies nested Python values.

**decision:** Preserve browser precedence, Other fallback, Python stringification, and null for malformed JSON rather than returning inferred JSON types.

**rationale:** The output remains comparable to the original Python paths.

**verification:** test:lakehouse/tests/test_users.py::test_users_spark_edges

**sources:** etl/spark/jobs.txt

## A-312 — Activity report inputs and consumers

**status:** open

**risk:** high

**legacy_objects:** etl_script:etl/scripts/user_activity_daily.py

**ambiguity:** The report uses analytics PostgreSQL and S3, not warehouse login activity, and the repo has no registered users BI or partner extract.

**decision:** Use a staged analytics-summary Parquet snapshot and the same dated gzip JSONL keys. Publish the three file outputs locally; live S3 publication, upstream staging and admin-reader cutover remain integration work.

**rationale:** The legacy report runs with real PostgreSQL query semantics and a local S3 double, not production credentials or services.

**verification:** users.activity_report

**sources:** etl/scripts/user_activity_daily.py

## A-313 — Activity report window, ranking and errors

**status:** accepted

**risk:** med

**legacy_objects:** etl_script:etl/scripts/user_activity_daily.py

**ambiguity:** The SQL window is inclusive of day minus 30; object reads use 30 day offsets and legacy catches all S3/JSON failures.

**decision:** Keep both windows, one contribution per source record, stable first-seen ranking, and skip absent optional objects; fail malformed or inaccessible input. Require one non-null summary per date.

**rationale:** Avoid publishing partial reports after hidden upstream errors. Empty user output omits JSONL and removes a stale copy on retry.

**verification:** users.activity_user_summaries

**sources:** etl/scripts/user_activity_daily.py

## A-314 — Activity timestamp and latest publication

**status:** accepted

**risk:** med

**legacy_objects:** etl_script:etl/scripts/user_activity_daily.py

**ambiguity:** Legacy stamps wall time and can move latest backwards during historical replay.

**decision:** Use UTC business-date midnight for generated_at, exclude that field from parity, and preserve highest published date for latest. Date-specific writes stage and rename each file.

**rationale:** Deterministic fixtures and one-active-run scheduling make retry predictable; multi-file object-store atomicity is not claimed.

**verification:** test:lakehouse/tests/test_users.py::test_report_publication_is_idempotent

**sources:** etl/scripts/user_activity_daily.py

## A-315 — Users schedule regrouping

**status:** open

**risk:** high

**legacy_objects:** cron_entry:etl/crontab#042e9e7fa551, cron_entry:etl/crontab#8256b4d51699, cron_entry:etl/crontab#9d492d3cabc6, cron_entry:etl/crontab#a1a53c82cfb3, cron_entry:etl/crontab#b8eef1610f31, cron_entry:etl/crontab#bb89194e6e7e, cron_entry:etl/crontab#d28d753c053a

**ambiguity:** Six Spark schedules run separately and the users report starts at 05:00 on the original batch host.

**decision:** Group the Spark jobs in one paused UTC daily graph and schedule the report in a separate paused daily graph. Use prior UTC business date with one retry and compare each output only after publication.

**rationale:** Demo backfills and task dependencies replace exact clock-time scheduling; the integration cutover must confirm feed SLAs and DAG activation.

**verification:** test:lakehouse/tests/test_users.py::test_users_graph_and_ownership

**sources:** etl/crontab

## A-400 — Daily BTEQ load is authoritative over Informatica alternatives

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/audit/01_load_events.bteq, bteq_script:warehouse/teradata/scripts/audit/03_load_reviews.bteq, informatica_mapping:SFX_AUDIT.m_SFX_STG_AUDIT_EVENT, informatica_session:SFX_AUDIT.s_m_SFX_STG_AUDIT_EVENT, informatica_mapping:SFX_AUDIT.m_SFX_AUDIT_EVENT, informatica_session:SFX_AUDIT.s_m_SFX_AUDIT_EVENT, informatica_mapping:SFX_AUDIT.m_SFX_SECURITY_ALERT, informatica_session:SFX_AUDIT.s_m_SFX_SECURITY_ALERT, teradata_table:SFX_AUDIT.AUDIT_EVENT, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/01_load_events, informatica_source:SFX_AUDIT.STG_AUDIT_EVENT, informatica_target:SFX_AUDIT.AUDIT_EVENT, teradata_table:SFX_AUDIT.STG_AUDIT_EVENT, informatica_source:SFX_AUDIT.FF_AUDIT_EVENT, informatica_source:SFX_AUDIT.AUDIT_EVENT, informatica_target:SFX_AUDIT.STG_AUDIT_EVENT, teradata_table:SFX_AUDIT.SECURITY_ALERT, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/03_load_reviews, informatica_source:SFX_AUDIT.FF_SECURITY_ALERT, informatica_target:SFX_AUDIT.SECURITY_ALERT

**ambiguity:** Informatica trims and uppercases events, replaces invalid IDs/details, and updates/escalates or rejects alerts; BTEQ truncates and inserts all staging rows unchanged.

**decision:** Use the BTEQ path actually dispatched by daily_chain. Do not apply Informatica trimming, default details, DD_UPDATE escalation, or severity rejects to these snapshots. Informatica identities are accounted for as superseded alternative producer semantics, not equivalent concurrent engines.

**rationale:** The requested system of record is the executed daily chain. Applying inactive alternative semantics would change final legacy outputs.

**verification:** test:lakehouse/tests/test_audit.py::test_daily_chain_does_not_apply_informatica_transformations

**sources:** warehouse/teradata/jobs/daily_chain, warehouse/teradata/scripts/audit/01_load_events.bteq, warehouse/teradata/scripts/audit/03_load_reviews.bteq, etl/informatica/repository/SFX_AUDIT/mappings/m_SFX_STG_AUDIT_EVENT.XML, etl/informatica/repository/SFX_AUDIT/mappings/m_SFX_AUDIT_EVENT.XML, etl/informatica/repository/SFX_AUDIT/mappings/m_SFX_SECURITY_ALERT.XML, etl/informatica/repository/SFX_AUDIT/wf_SFX_AUDIT_DAILY.XML

## A-401 — Audit-local count projections until other domain models merge

**status:** accepted

**risk:** med

**legacy_objects:** bteq_script:warehouse/teradata/scripts/audit/11_reconciliation.bteq, teradata_table:SFX_AUDIT.AUDIT_RECON, teradata_view:SFX_AUDIT.V_EVENT_ACTORS

**ambiguity:** Fetched remote branches and open lakehouse PRs expose only the foundation customer_account silver model; most external base models are absent.

**decision:** Use ref(customer_account) now. For absent models use audit-local ephemeral typed bronze projections with the legacy row-selection rules, including latest document version, SET storage deduplication, user activity generation, monthly billing usage and invoice-line additions. Explicit DAG edges require all three bronze domains and dbt_billing. Swap these projections to domain ref() dependencies once their models merge.

**rationale:** Counts must describe final base state rather than assume every base count equals staging. This does not claim ownership or full conversion of external domains.

**verification:** audit.audit_recon

**sources:** warehouse/teradata/scripts/audit/11_reconciliation.bteq, warehouse/teradata/jobs/daily_chain, warehouse/teradata/procedures/activity_daily.sql, warehouse/teradata/scripts/documents/02_current_versions.bteq, warehouse/teradata/scripts/documents/05_load_sessions.bteq, warehouse/teradata/scripts/documents/10_storage_monthly.bteq, warehouse/teradata/procedures/monthly_invoice.sql

## A-402 — Exclude the one shared reconciliation runner row

**status:** accepted

**risk:** low

**legacy_objects:** bteq_script:warehouse/teradata/scripts/audit/11_reconciliation.bteq, teradata_table:SFX_AUDIT.AUDIT_RECON, teradata_view:SFX_AUDIT.V_CUSTOMER_RECON, teradata_macro:SFX_AUDIT.M_RECON_TOTALS

**ambiguity:** The full chain writes recon_id 21000000001 through shared jobs/reconcile; that responsibility is handed to integration.

**decision:** Exclude exactly recon_id=21000000001 from both comparison populations and audit publication. Preserve every audit-generated 20000000001..20000000037 row and every other load row. Number the ordered multiset for the customer-recon view because it exposes no unique key.

**rationale:** User explicitly assigned shared runner output to integration; this is an ownership filter, not numerical tolerance or hidden mismatch.

**verification:** audit.audit_recon

**sources:** warehouse/teradata/jobs/reconcile, warehouse/teradata/jobs/daily_chain, warehouse/teradata/scripts/audit/11_reconciliation.bteq, warehouse/teradata/ddl/audit/10_views.sql

## A-403 — Disabled archive defaults and enabled replay limitation

**status:** open

**risk:** high

**legacy_objects:** teradata_table:SFX_AUDIT.AUDIT_EVENT_ARCHIVE, informatica_mapping:SFX_AUDIT.m_SFX_AUDIT_EVENT_ARCHIVE, informatica_session:SFX_AUDIT.s_m_SFX_AUDIT_EVENT_ARCHIVE, teradata_macro:SFX_AUDIT.M_ARCHIVE_OVERVIEW

**ambiguity:** Archive task is disabled, with 2555-day session override and a non-resetting sequence; an enabled production run would append and advance persisted sequence state.

**decision:** Default audit_archive_enabled=false produces empty archive, matching the fresh legacy fixture. Enabled model selects events strictly older than business date minus 2555 days and assigns deterministic event-ID-ordered row numbers from 1. Enabled snapshots are not a migration of prior archive history or persistent Informatica sequence state.

**rationale:** Requested gated implementation is replayable and testable; no wall-clock dependency is introduced. Persistent enabled append/sequence equivalence remains explicitly unverified. Archive mapping/session coverage replaces only the disabled scheduling responsibility under A-408, not enabled history migration.

**verification:** test:lakehouse/tests/test_audit.py::test_summary_final_and_archive_gate

**sources:** etl/informatica/repository/SFX_AUDIT/wf_SFX_AUDIT_DAILY.XML, etl/informatica/repository/SFX_AUDIT/mappings/m_SFX_AUDIT_EVENT_ARCHIVE.XML, etl/informatica/params/sfx_d1110_daily.par

## A-404 — Final chain summaries and reconciliation override load snapshots

**status:** accepted

**risk:** low

**legacy_objects:** teradata_table:SFX_AUDIT.AUDIT_DAILY_SUMMARY, teradata_table:SFX_AUDIT.AUDIT_RECON, teradata_procedure:SFX_AUDIT.P_DAILY_SUMMARY, teradata_procedure:SFX_AUDIT.P_RECON_COUNTS, informatica_mapping:SFX_AUDIT.m_SFX_AUDIT_DAILY_SUMMARY, informatica_session:SFX_AUDIT.s_m_SFX_AUDIT_DAILY_SUMMARY, bteq_script:warehouse/teradata/scripts/audit/03_load_reviews.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/03_load_reviews, bteq_script:warehouse/teradata/scripts/audit/10_summary_daily.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/10_summary_daily, bteq_script:warehouse/teradata/scripts/audit/11_reconciliation.bteq, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/11_reconciliation

**ambiguity:** Load snapshot tables are later changed by report procedures. Informatica summary instead counts DOC_EXPORT and uses a sequence.

**decision:** Keep load rows in silver. Gold summary preserves IDs below 10000000000 and appends business-day customer counts with synthetic IDs and zero exports. Gold recon replaces the 37 audit count IDs, then recomputes differences only for the business day. Informatica summary remains pending as an alternative producer.

**rationale:** Final full-chain legacy parity, rather than intermediate load-stage parity, is the requested contract.

**verification:** audit.audit_daily_summary

**sources:** warehouse/teradata/scripts/audit/03_load_reviews.bteq, warehouse/teradata/scripts/audit/10_summary_daily.bteq, warehouse/teradata/scripts/audit/11_reconciliation.bteq, warehouse/teradata/procedures/summary_daily.sql, warehouse/teradata/procedures/recon_counts.sql, etl/informatica/repository/SFX_AUDIT/mappings/m_SFX_AUDIT_DAILY_SUMMARY.XML

## A-405 — Atomic date-scoped reconciliation publication

**status:** accepted

**risk:** low

**legacy_objects:** bteq_script:warehouse/teradata/scripts/audit/11_reconciliation.bteq, teradata_macro:SFX_AUDIT.M_RECON_TOTALS

**ambiguity:** Legacy exports a mutable reconciliation.psv with no header and rows ordered by recon ID; the file contains a shared runner row outside audit ownership.

**decision:** Publish the audit-owned macro projection as exports/<business_date>/reconciliation.psv, same four integer columns and ordering, excluding only A-402 shared ID. Write and fsync a same-directory temporary file then os.replace; failures preserve the previous publication and retries replace it. File parity compares the scoped legacy macro SQL to the published file.

**rationale:** Date scoping supports replay/backfill and atomic replacement avoids partial output; no claim is made to integration-owned file rows.

**verification:** test:lakehouse/tests/test_audit.py::test_export_empty_retry_and_failure

**sources:** warehouse/teradata/scripts/audit/11_reconciliation.bteq, warehouse/teradata/macros/recon_totals.sql, warehouse/teradata/jobs/reconcile

## A-406 — Spark snapshot feeds and Delta replace Parquet plus JDBC sinks

**status:** accepted

**risk:** med

**legacy_objects:** spark_job:audit_actor_activity_join, spark_job:audit_archive_resort, spark_job:audit_daily_summary, spark_job:compliance_flag_rules, spark_job:lake_compaction_audit, spark_job:security_alert_anomaly, spark_submit:etl/spark/submit/audit_actor_activity_join.sh, spark_submit:etl/spark/submit/audit_archive_resort.sh, spark_submit:etl/spark/submit/audit_daily_summary.sh, spark_submit:etl/spark/submit/compliance_flag_rules.sh, spark_submit:etl/spark/submit/lake_compaction_audit.sh, spark_submit:etl/spark/submit/security_alert_anomaly.sh

**ambiguity:** The Spark estate uses headered feeds with different schemas from warehouse landing; legacy jobs read all files in each table directory and publish both Parquet and optional JDBC copies.

**decision:** Use the separate Spark fixture/production landing snapshot selected by AUDIT_SPARK_LANDING (default etl/spark/.data/<LEGACY_NS>/landing), identical for both Spark engines. Preserve every landed row, stamp the explicit BUSINESS_DATE batch into bronze_audit.spark_* and publish gold_audit.spark_* Delta snapshots instead of duplicate Parquet/JDBC sinks. Cross-domain user feeds are declared dependencies. Sorting/file layout are physical, not relational outputs; Delta OPTIMIZE replaces coalescing. Allow only 1e-10 absolute Z-score error for parallel floating reduction ordering. Backfills require a frozen matching Spark source directory.

**rationale:** Schema guessing or reusing the incompatible warehouse feeds would compare different data. Local legacy submit scripts and converted outputs run against the exact same Spark fixture.

**verification:** audit.spark_audit_daily_summary

**sources:** etl/spark/jobs/py/common/schemas.py, etl/spark/jobs/py/common/runtime.py, etl/spark/fixture/generate_fixture.py, etl/spark/scala/src/main/scala/sfx/BatchSupport.scala, etl/spark/jobs/py/lake_compaction_audit.py, etl/spark/jobs/py/security_alert_anomaly.py

## A-407 — Business-date weekly archive with resumable publication and deletion

**status:** accepted

**risk:** med

**legacy_objects:** etl_script:etl/scripts/audit_archive_weekly.py, cron_entry:etl/crontab#33854636d6ba

**ambiguity:** Legacy uses UTC wall-clock midnight minus 90 days, nondeterministic gzip headers/report time, overwrites the weekly key, and swallows deletion failures.

**decision:** Use BUSINESS_DATE midnight UTC minus 90 days with the same strict timestamp-string cutoff. Canonically sort JSONL and use deterministic gzip; report generated_at is business-date midnight. Compare decompressed event multisets and all report fields except generated_at/compressed_size_bytes against the frozen-clock legacy script. Publish Glacier first, then a conditional Standard manifest of immutable event keys and SHA256, then delete, then conditionally publish the report. Retry resumes the manifest without reading Glacier; an existing completed report is immutable. Require immutable DynamoDB event keys/content during archival and explicit bucket/owner configuration. New late arrivals for an already published business date wait for the next weekly run; a conflicting incomplete snapshot fails closed.

**rationale:** Avoids partial-file exposure, silent deletion loss and needing Glacier restoration on retry; the safety improvement is deliberate, not hidden parity normalization. Extra manifests contain keys, not event payloads.

**verification:** test:lakehouse/tests/test_audit_archive.py::test_archive_legacy_file_parity

**sources:** etl/scripts/audit_archive_weekly.py, etl/crontab

## A-408 — Audit schedules and inactive Informatica alternatives converge on Airflow

**status:** accepted

**risk:** med

**legacy_objects:** cron_entry:etl/crontab#21215b59c160, cron_entry:etl/crontab#33854636d6ba, cron_entry:etl/crontab#77635c543e02, cron_entry:etl/crontab#949f96b6edeb, cron_entry:etl/crontab#ae80e15b906a, cron_entry:etl/crontab#d0caaba38c97, cron_entry:etl/crontab#d793014c2fb2, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/01_load_events, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/02_load_controls, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/03_load_reviews, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/10_summary_daily, cron_entry:warehouse/teradata/jobs/daily_chain#stage=audit/11_reconciliation, informatica_config:SFX_AUDIT.default_session_config, informatica_mapping:SFX_AUDIT.m_SFX_AUDIT_DAILY_SUMMARY, informatica_mapping:SFX_AUDIT.m_SFX_AUDIT_EVENT_ARCHIVE, informatica_scheduler:SFX_AUDIT.wf_SFX_AUDIT_DAILY.Scheduler, informatica_session:SFX_AUDIT.s_m_SFX_AUDIT_DAILY_SUMMARY, informatica_session:SFX_AUDIT.s_m_SFX_AUDIT_EVENT_ARCHIVE, informatica_target:SFX_AUDIT.AUDIT_DAILY_SUMMARY, informatica_target:SFX_AUDIT.AUDIT_EVENT_ARCHIVE, informatica_task:SFX_AUDIT.wf_SFX_AUDIT_DAILY.Start, informatica_workflow:SFX_AUDIT.wf_SFX_AUDIT_DAILY

**ambiguity:** Legacy audit tasks have independent cron times, Informatica daily 03:00 scheduling/session settings, an inactive archive session, and alternative summary semantics.

**decision:** Converge active SQL and Spark snapshots into the UTC @daily dependency graph. Use a separate UTC @weekly (Sunday 00:00 timetable) audit archive DAG, with BUSINESS_DATE equal to logical date minus one day per the guide (Sunday logical date archives as of Saturday). Dependency success, one active run/task, retries and namespace locking replace workflow Start/config controls; no independent Informatica task is dispatched. Summary alternatives use the A-404 authoritative final SQL output. Archive mapping/session/target metadata replaces only its disabled scheduling responsibility and default-false model gate; enabled persistent append/sequence equivalence remains unverified under open A-403.

**rationale:** A named Airflow DagBag/template test verifies cadence, success gating, source edges and date semantics. Replaced disabled responsibility is not a claim that an enabled persistent archive migration is complete.

**verification:** test:lakehouse/airflow/tests/test_dags.py::test_audit_owned_schedule_and_dependencies

**sources:** etl/crontab, warehouse/teradata/jobs/daily_chain, etl/informatica/repository/SFX_AUDIT/wf_SFX_AUDIT_DAILY.XML, etl/informatica/params/sfx_d1110_daily.par
