# 07_dependency_register.md

| Class | Item | State | Notes |
|---|---|---|---|
| D1 Other writers | PL/SQL packages pkg_plans, pkg_rating, pkg_invoicing, pkg_dunning | FOUND | write subscriptions, rating_*, invoices, invoice_lines, dunning_attempts, notifications |
| D1 Other writers | triggers trg_customer_master_hist, trg_subscriptions_hist, trg_*_seq, trg_sub_no_uncancel | FOUND | history copies and synthetic keys are trigger-maintained |
| D2 Other readers | services/legacy-billing/app/reports.py (RPT-114 month-end reconciliation reads CUSTOMER_MASTER via oracledb) | FOUND | |
| D2 Other readers | procs/harness parity recorder (procs/oracle/oracle_map.yaml) | FOUND | |
| D3 Scheduled logic | DBMS_SCHEDULER JOB_NIGHTLY_DUNNING (02:00), JOB_PURGE_AUDIT_LOG (03:30) | FOUND | created disabled in the estate |
| D4 Access | production source read-only principal, Atlas migration cluster | NOT APPLICABLE | offline mode |
