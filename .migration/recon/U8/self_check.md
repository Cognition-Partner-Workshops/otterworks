# U8 pre-PR self-check

Skill: `.agents/skills/tp-pre-pr-self-check/SKILL.md`
Unit: U8
Run: fixture mode, 2026-09-02 UTC

| Check | Result | Evidence / coverage |
|---|---|---|
| NULL and missing attribution cannot fail open | PASS | `InvoicingIntegrityError` validates invoice fields before the first invoice write; `services/legacy-billing/tests/test_invoicing.py` covers the rejected NULL-plan-code path. |
| Target references are unit-scoped and prefixed | PASS | Loader writes only `replay_u8_*` collections in `ow_tp_mongodb_205236`; the sibling `replay_u9_subscriptions_history` observation is recorded separately and was untouched. |
| No DDL drops/replaces/alters shared tables | PASS | `load_u8.py` scopes drop/recreate and `$out` operations to `replay_u8_*`; shared golden collection counts remained unchanged. |
| Rerun cleanup is safe and does not remove newer-run data | PASS | Two actual U8 loads completed; `u8.recon.json` reports idempotency `pass`. |
| Cleanup retains run evidence and recon artifacts | PASS | `load_report.run1.json`, `load_report.json`, `mapping/u8.json`, `result.json`, `report.md`, `recon.summary.md`, `tier4_provenance.json`, and `u8.recon.json` are present. |
| No secrets, tokens, or real distribution-list/email addresses | PASS | Secret-pattern scan of `.migration/recon/U8` found no DSNs, credentials, MongoDB URIs, or email addresses. |
| Parity-versus-tolerance decision matches contract | PASS | `result.json` reports mapping `v1.0.1`, tolerance `v1`, and harness verdict `PASS`; frozen mapping, tolerance, and canonicalization files were not changed. |
| Idempotency proven by actual rerun | PASS | Run 1/run 2 load reports compare equal for collection counts, indexes, and embedded counts. |
| Recon values recomputed from target platform | PASS | `u8.recon.json` sets `values_recomputed_from_target: true`; report checks use target `count_documents` and aggregation results. |
| Every unverified/untested path is listed | PASS | `u8.recon.json` lists the parent LIVE gate, transcript provenance, transaction/partial-failure, branch coverage, HTTP, audit-log, concurrency, and sibling-collection paths. |
| Recon report schema and artifact | PASS | `u8.recon.json` declares `"kind": "recon-report"`; `make tp-validate-recon FILE=.migration/recon/U8/u8.recon.json` passed. |
| Capability preflight | PASS | `recon` import was installed and verified; `MONGODB_ATLAS_URI` was set; Oracle fixture answered; no `replay_u8_*` collision existed before loading. |
| `make tp-smoke` | PASS | `tp-smoke: all checks passed` (`/home/ubuntu/u8-tp-smoke.log`). |

U8 fixture evidence: T1 8/8, T2 36/36, T3 902/902 including 2 embedded invoice
lines, and T4 6/6 invoicing scenarios. The parent-owned LIVE gate remains
unverified.
