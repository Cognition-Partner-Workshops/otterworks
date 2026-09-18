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
