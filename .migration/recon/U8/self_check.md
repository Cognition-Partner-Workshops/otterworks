# U8 pre-PR self-check

Skill: `.agents/skills/tp-pre-pr-self-check/SKILL.md`
Unit: U8
Run: fixture mode, 2026-09-02 UTC

| Check | Result | Evidence / coverage |
|---|---|---|
| NULL and missing attribution cannot fail open | PASS | `InvoicingIntegrityError` validates invoice fields before the first invoice write and again inside the transaction; `services/legacy-billing/tests/test_invoicing.py` covers the rejected NULL-plan-code path. |
| Target references are unit-scoped and prefixed | PASS | Loader writes only `replay_u8_*` collections in `ow_tp_mongodb_205236`; the sibling `replay_u9_subscriptions_history` observation is recorded separately and was untouched. |
| No DDL drops/replaces/alters shared tables | PASS | `load_u8.py` scopes drop/recreate and `$out` operations to `replay_u8_*`; shared golden collection counts remained unchanged. |
| Rerun cleanup is safe and does not remove newer-run data | PASS | Two additional actual U8 loads completed at the current HEAD; `u8.recon.json` reports idempotency `pass`. |
| Cleanup retains run evidence and recon artifacts | PASS | `load_report.run1.json`, `load_report.json`, `result.run1.json`, `mapping/u8.json`, `result.json`, `report.md`, `recon.summary.md`, `recon.summary.run1.md`, `tier4_provenance.json`, and `u8.recon.json` are present. |
| No secrets, tokens, or real distribution-list/email addresses | PASS | Secret-pattern scan of `.migration/recon/U8` found no DSNs, credentials, MongoDB URIs, or email addresses. |
| Parity-versus-tolerance decision matches contract | PASS | `result.json` reports mapping `v1.0.1`, tolerance `v1`, and harness verdict `PASS`; frozen mapping, tolerance, and canonicalization files were not changed. |
| Idempotency proven by actual rerun | PASS | Run 1/run 2 load reports compare equal for collection counts, indexes, and embedded counts. |
| Recon values recomputed from target platform | PASS | `u8.recon.json` sets `values_recomputed_from_target: true`; report checks use target `count_documents` and aggregation results. |
| Every unverified/untested path is listed | PASS | `u8.recon.json` lists the parent LIVE gate, transcript provenance, transaction boundary/partial-failure, branch coverage, HTTP, audit-log, concurrency, and sibling-collection paths. |
| Recon report schema and artifact | PASS | `u8.recon.json` declares `"kind": "recon-report"`; `make tp-validate-recon FILE=.migration/recon/U8/u8.recon.json` passed. |
| Capability preflight | PASS | `MONGODB_ATLAS_URI` presence was verified without disclosure; the inline Oracle fixture DSN connected; required dependencies were available; both loads and the live harness recon completed. The harness required the locally-created, uncommitted `.migration/allowed_targets.json`; a transient `DPY-6005` connection refusal occurred during a later read, then the read-only container-local check returned `SELECT COUNT(*) FROM invoices = 3`. |
| `make tp-smoke` | PASS | `tp-smoke: all checks passed`. |

U8 fixture evidence, recon run 2/3: T1 8/8, T2 36/36, T3 902/902 including 2
embedded invoice lines, and T4 6/6 invoicing scenarios. The parent-owned
LIVE gate remains unverified.

## Regression gates

- **U7: PASS** — full harness run (the harness has no tier-selection option): T1 5/5, T2 23/23, T3 892/892, T4 8/8. Output: `.migration/recon/U8/regression/U7/result.json`.
- **U5: FAIL (pre-existing drift, not owned by U8-fix)** — the remaining 10 T1 checks passed; all T2/T3 checks passed. The single failure is verbatim: `T1 billing_audit_log root_count: rows(BILLING_AUDIT_LOG)=0 vs docs=1`. This matches the U5 ledger row's recorded source-drift row and the unchanged golden `billing_audit_log` snapshot (1 → 1); U8 did not write the golden audit log. Output: `.migration/recon/U8/regression/U5/result.json`.
- **Counters:** the `seq_billing_audit_log` / `seq_subscriptions_hist` seed values graded equal in both regression contexts at load time (`1` / `61`); U7's replay-local audit counter advanced independently to 9 across its eight rating writes, while the golden counter remained 1.
- **Harness preflight:** `.migration/allowed_targets.json` was absent on the branch and was created locally, uncommitted, with the two approved databases only.
- **Oracle connectivity:** a transient `DPY-6005: cannot connect to database ... [Errno 111] Connection refused` occurred during a read-only probe; the subsequent container-local read-only query returned `SELECT COUNT(*) FROM invoices = 3`.
