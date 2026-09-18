# 05_decisions.md

| Date | Decision | Answer | Approved by | Provenance |
|---|---|---|---|---|
| 2026-09-18 | Recon mode | offline (DDL + local fixture only; no Atlas, no MCP) | run brief | FACT |
| 2026-09-18 | Target database | local mongo:7, database ow_billing only | run brief | FACT |
| 2026-09-18 | Stop mode | hard for A, B, C | run brief | FACT |
| 2026-09-18 | Tolerances tol-1 | strict defaults from oracle profile (see 02_tolerances.md) | parent approver, STOP A | FACT |
| 2026-09-18 | Empty string policy | empty VARCHAR2 loads as missing field; recon `null_missing_equiv` | parent approver, STOP A | FACT |
| 2026-09-18 | String date policy | DD-MON-YY parsed to date; unparseable kept verbatim in `<field>_raw` and counted, never dropped | parent approver, STOP A | FACT |
| 2026-09-18 | Source and target access probes | NOT APPLICABLE in offline mode; offline_guard.py OK is the recorded evidence | playbook 1 step 5 | FACT |
| 2026-09-18 | STOP A | APPROVE: conventions, tol-1, offline recon mode, ow_billing as the only target, all as written | parent approver | FACT |
| 2026-09-18 | Model map-1 (11 cited decisions, see 05_decisions.json) | INVOICE_LINES embedded in invoices as `lines` (1:few, derived, pkg_invoicing); ENTITY_ATTR_VALUE attribute pattern, values kept as strings; CUSTOMER_MASTER_HIST and SUBSCRIPTIONS_HIST history_copy archive collections, app-written after cutover; CODES reference_data; INVOICE_HEADER / INVOICE_LINE stay referenced (37 orphan lines, RPT-114 join drops them); element key LINE_NO | pending STOP B | PROPOSED |
| 2026-09-18 | Census agreement | script census vs DBMS_METADATA dump census: 19 tables, 431 columns, 13 FKs identical; dump has one extra table FIXTURE_META (container bootstrap marker, not billing schema, not migrated) | playbook 2 step 2 | FACT |
| 2026-09-18 | Deterministic replay | census, proposal, patch re-run: census.json and 03_mapping_spec.json byte-identical (sha256 513833c0...) | playbook 2 step 5 | FACT |
| 2026-09-18 | STOP B | APPROVE map-1 and the 11 decisions. Walkthrough must state plainly why invoice lines embed but INVOICE_HEADER/INVOICE_LINE stay referenced (37 orphans, RPT-114 join). Negative control once during unit migration. | parent approver | FACT |
| 2026-09-18 | Naming convention | 01_conventions.md originally said snake_case; map-1 as generated and approved at STOP B uses camelCase collection and field names. Conventions aligned to the approved model rather than renaming 18 collections after approval. Smallest reasonable assumption, no re-approval requested. | unit PR review, w1-customers | ASSUMED |
