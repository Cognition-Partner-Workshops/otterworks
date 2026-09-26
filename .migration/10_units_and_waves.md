# 10 Units and wave plan

Unit = one source collection moved to `mmp_rt_billing_n` with index parity and a recon PASS.
No unit embeds or joins another (identity lift), and referential checks (M1) read the source only,
so every unit sits at dependency depth 0 and no wave-0 shared/reference step exists. Batches are
whole collections: no `${param}` scoping.

| Unit | Rows | Size | Batch | Write targets (`mmp_rt_billing_n.`) | Notes |
|---|---|---|---|---|---|
| users | 500 | S | w1-b01 | users | M3 dup e-mails kept; `email_1` non-unique |
| folders | 300 | S | w1-b01 | folders | 119 null parentId |
| documents | 5000 | M | w1-b02 | documents | Decimal128 price; 5 null folderId |
| comments | 12000 | M | w1-b03 | comments, _dq_comments_orphans | M1 orphan work-list |
| shares | 3000 | S | w1-b04 | shares | field names per census |
| audit_events | 20000 | M | w1-b05 | audit_events | M4 string ts -> date |

Wave 1: 5 batches, width 3 (fan-out via `migration-fanout` workflow, Cloud `run_workflow`),
`auto_merge: true` (stop_mode soft), breaker 3, child_minutes 45. No XL units, no wave 2.
Manifest: `.migration/waves/wave-1.json`. Fixture manifests: `.migration/fixtures/w1-b0N.json`.
Unit code lands under `migration/mmp_rt/<batch-id>/` (one directory per batch; no shared files, so
PRs cannot conflict); child recon evidence under `migration/mmp_rt/<batch-id>/recon/` (children may
not write under `.migration/`; the verifier's report goes to `.migration/recon/wave-1/` on its own
branch as the workflow prescribes).
