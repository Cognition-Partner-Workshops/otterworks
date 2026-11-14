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
| billing_audit_log | 139 | 139 | accepted difference with reason | logged_at: SYSDATE / LOCALTIMESTAMP at write time |
| subscriptions_hist | 3 | 3 | accepted difference with reason | hist_dt: SYSDATE / now() at write time |
| fixture_meta | 2 | 2 | identical | all columns, order-independent checksum |
| customer_master | 25001 | 25001 | identical | all columns, order-independent checksum |
| customer_master_hist | 0 | 0 | identical | all columns, order-independent checksum |
| entity_attr_value | 8337 | 8337 | identical | all columns, order-independent checksum |
| invoice_header | 18750 | 18750 | identical | all columns, order-independent checksum |
| invoice_line | 150000 | 150000 | identical | all columns, order-independent checksum |
