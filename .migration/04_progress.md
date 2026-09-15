# 04 Progress

Units and waves, derived from the census (`census.md`) and the PRD delivery order.
Status values: PLANNED, RUNNING, PASS, FAIL, HALTED.

| Unit | Wave | Batch | Status | Parity | Quarantine rate | Unverified paths | PR |
|---|---|---|---|---|---|---|---|
| plans, codes, tenants, subscription_history (U1-reference) | 0 | w0-b01 | PASS | live recon PASS, tiers 1-4, 0 findings | 0 | 4 (tier 4 grading for flags/CSV/date-strings and CODES decodes; empty `subscription_history`; no `ow_tp` prefix; demo scale) | #1563 merged |
| customers, customer_history | 1 | w1-b01 | PASS | live recon PASS, child and independent verifier; 25,000 customers, 8,333 embedded attributes, empty history | 50 bad `SIGNUP_DT` + 31 bad CSV kept raw (in budget) | array-index paths and CODES decodes graded by tier 4 | #1567 merged |
| invoices, invoice_lines_orphaned | 1 | w1-b02 | PASS | live recon PASS, child and independent verifier; 18,753 invoices (18,750 conversion + 3 billing), 149,965 embedded lines | 37 orphaned lines (in budget) | two source roots in one collection graded through a unit-local recon spec; 68,340 backwards service periods carried unchanged | #1568 merged |
| usage_events, rating_periods | 1 | w1-b03 | PASS | live recon PASS, child and independent verifier; 814 usage events, 3 rating periods | 0 | Y/N, CSV and date-string fields graded by tier 4 | #1565 merged |
| credit_notes, notifications, audit_log | 1 | w1-b04 | PASS | live recon PASS, child and independent verifier; 5 credit notes, 1 notification, empty audit log | 0 | CODES-decoded `notifications.kind` graded by tier 4; `audit_log` empty at source so its TTL is untested | #1564 merged |

Wave 0 is one batch, so it runs in-session (`!mongo_unit_migration` then
`!mongo_reconciliation`), per the orchestrator playbook's small-wave rule. Wave 1 is four
batches, so it runs through the `migration-fanout` workflow at width 4.

Expected row counts per unit are in each batch brief and in `03_mapping_spec.json`
under `cardinality`.
