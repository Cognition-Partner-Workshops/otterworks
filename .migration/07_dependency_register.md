# 07_dependency_register — who else touches OW_BILLING

States: FOUND → DECIDED (owner and plan named) → DONE. Initial rows from the DDL and code read at Setup; completed by the census in playbook 2. Citations are `file:line` on `tech-partnerships`.

| ID | Class | Item | Evidence | State | Owner / plan |
|---|---|---|---|---|---|
| DEP-01 | D3 Scheduled logic | `JOB_NIGHTLY_DUNNING` 02:00 daily → `pkg_dunning.sp_schedule_dunning` + `sp_suspend_overdue` (created DISABLED) | `services/legacy-billing/db/oracle/schema/04_jobs.sql:10-17` | FOUND | |
| DEP-02 | D3 Scheduled logic | `JOB_PURGE_AUDIT_LOG` 03:30 daily, 90-day retention hardcoded | `schema/04_jobs.sql:21-28` | FOUND | |
| DEP-03 | D3 Trigger | `trg_subscriptions_hist` full-row copy on UPDATE/DELETE, string timestamp | `schema/01_tables.sql:206-224` | FOUND | |
| DEP-04 | D3 Trigger | `trg_sub_no_uncancel` business rule (status 30 sticky) | `schema/01_tables.sql:228-236` | FOUND | |
| DEP-05 | D3 Trigger | `trg_usage_events_check` (units > 0, kind in CODES) | `schema/01_tables.sql:239-254` | FOUND | |
| DEP-06 | D3 Trigger | sequence-identity triggers `trg_billing_audit_log_id`, `trg_customer_master_seq`, `trg_entity_attr_value_seq`; `trg_customer_master_hist` | `schema/01_tables.sql:179-187`, `schema/02_horror.sql:346-399` | FOUND | |
| DEP-07 | D3 Scheduled logic | cron (`etl/legacy-extra/crontab`): `sftp_ingest_poll.ksh` */15, `parse_custbill_fixedwidth.sh`, `finance_excel_report.pl` 02:10, `run_all.sh` Sun 06:00 — file jobs downstream of the Oracle extract | `etl/legacy-extra/crontab` | FOUND | |
| DEP-08 | D1 Other writers | PL/SQL packages `pkg_plans`, `pkg_rating`, `pkg_invoicing`, `pkg_dunning`, `pkg_ow_util.log_msg` (autonomous tx) write invoices, invoice_lines, rating_periods/results, credit_notes, dunning_attempts, notifications, subscriptions(_hist), billing_audit_log | `packages/0[1-5]_*.sql` | FOUND | |
| DEP-09 | D1 Other writers | Facade direct SQL: `ensure_tenant` INSERT tenants + subscriptions; `change_plan` UPDATE subscriptions; `/internal/usage/events` INSERT usage_events (fed by the SQS bridge) | `services/legacy-billing/app/backends/oracle.py:67-75,136-161`, `app/facade.py:390-412`, `bridge/bridge.py:190-223` | FOUND | |
| DEP-10 | D1 Other writers | Seed/load tooling writes customer_master(_hist), entity_attr_value, invoice_header, invoice_line and core tables; parity recorder resets core tables | `testdata/legacy/oracle_billing_seed.py:80-361`, `procs/harness/oracle_record.py:42-56` | FOUND | |
| DEP-11 | D2 Other readers | Facade reads tenants+codes, customer_master + entity_attr_value (two queries, app-side stitch), usage_events+codes, invoices+rating_periods+codes, dunning_attempts+codes | `app/facade.py:110-128,211-224,240-251,286-299,337-349` | FOUND | |
| DEP-12 | D2 Other readers | Month-end report RPT-114: invoice_header ⋈ invoice_line ⋈ codes (inner join drops orphan lines), customer_master balances by conversion_batch_no | `app/reports.py:42-89,159-206`; `docs/tech-partnerships/billing-report-contract.md:30` | FOUND | |
| DEP-13 | D2 Other readers | CUSTBILL extract: invoice_header ⋈ customer_master ⋈ tenants, `TO_DATE(invoice_dt,'DD-MON-RR')`, fixed-width `.dat` out | `etl/legacy-extra/tools/oracle_custbill_extract.py:15-28,93-124`; `Makefile:634-648` | FOUND | |
| DEP-14 | D2 Other readers | Parity probes and ops probes: `procs/oracle/oracle_map.yaml:27-180`, `scripts/tp_pain/mongodb.py:107-179`, `Makefile:124-126` | as cited | FOUND | |
| DEP-15 | D2 Other readers | Frontend renders EAV rows and CSV fields verbatim over HTTP (no parsing) | `frontend/client-app/src/features/billing/api.ts:137`, `account-page.tsx:55` | FOUND | |
| DEP-16 | D4 Access | Source RO principal, egress, query cap — OPEN (see `06_access_checklist.md`) | offline run | FOUND | customer, before LIVE/SNAPSHOT recon |
