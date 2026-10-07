| Table | Oracle rows | Postgres rows | Result | Detail |
| --- | ---: | ---: | --- | --- |
| codes | 32 | 32 | identical | all columns, order-independent checksum |
| tenants | 72 | 72 | identical | all columns, order-independent checksum |
| plans | 3 | 3 | identical | all columns, order-independent checksum |
| subscriptions | 74 | 74 | identical | all columns, order-independent checksum |
| usage_events | 819 | 819 | identical | all columns, order-independent checksum |
| rating_periods | 14 | 14 | identical | all columns, order-independent checksum |
| rating_results | 14 | 14 | identical | all columns, order-independent checksum |
| invoices | 15 | 15 | identical | all columns, order-independent checksum |
| invoice_lines | 59 | 59 | identical | all columns, order-independent checksum |
| credit_notes | 5 | 5 | identical | all columns, order-independent checksum |
| dunning_attempts | 5 | 5 | identical | all columns, order-independent checksum |
| notifications | 2 | 2 | identical | all columns, order-independent checksum |
| billing_audit_log | 140 | 134 | accepted difference with reason | every Postgres (module, message) row has an Oracle twin; log_id/logged_at are sequence/wall-clock. Oracle-only rows come from calls that failed after logging (LOG_MSG is autonomous on Oracle, transactional on Postgres): 5 x PLANS: sp_change_plan tenant=fbd4c57e-8413-fb09-5842-22c318e2a5af plan=10000000-0000-0000-0000-000000000002 eff=2026-12-01, 1 x RATING: compute tenant=fbfef46c-1c83-389e-d1cc-3108d4e8e0be used=0 billable=0 |
| subscriptions_hist | 3 | 3 | accepted difference with reason | hist_dt: SYSDATE / now() at write time |
| fixture_meta | 2 | 2 | identical | all columns, order-independent checksum |
| customer_master | 25001 | 25001 | identical | all columns, order-independent checksum |
| customer_master_hist | 0 | 0 | identical | all columns, order-independent checksum |
| entity_attr_value | 8337 | 8337 | identical | all columns, order-independent checksum |
| invoice_header | 18750 | 18750 | identical | all columns, order-independent checksum |
| invoice_line | 150000 | 150000 | identical | all columns, order-independent checksum |
