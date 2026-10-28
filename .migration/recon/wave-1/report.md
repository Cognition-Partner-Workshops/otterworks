# Wave 1 recon report — run 1793185083

**OUT-OF-BAND VERIFICATION — NOT CONSUMED BY THE FAN-OUT.** Plugin 0.6.2 cannot produce
merge authority for these batches (`migration-fanout/workflow.py:run_batch` downgrades a
FAIL-verdict batch before reading its `merge_override`, so the fan-out skipped verify);
this report is independent evidence only. Nothing merges on it.

- Verifier: devin-9ee686c2aa1044afae35f9f23fa1978a (ticket UNT18-15)
- Base: `tp-run/databricks-1793185083` @ `db5266da6`; tolerances `tol-20261027-v1` and
  `allowed_targets.json` read from the base branch, byte-identical on both batch PR heads.
- Harness: `skills/data-reconciliation` @ plugin 0.6.2, fresh venv, `dbx-recon selftest` PASS.
- Mode `live`, depth `full` (manifest `verify_depth=full`), seed `20261028` (children used `0`).
- Guard probe `__dbx_guard_probe__` confirmed BLOCKED before any run; no guard block was hit
  during verification. Source and targets stayed read-only.

## Wave verdict: PASS (evidence-only)

| Batch | Unit | Depth | Parity | Blockers (classes) | Verdict | Authority |
|---|---|---|---|---|---|---|
| b1-plans | u-plans → Lakebase `ow_tp` @ `mig-1793185083` | full | PASS | `trigger_extra` ×3 (structural) | **PASS** | `mo-plans-trigger-visibility` |
| b1-quality | u-invoice-quality-pipeline → `ow_tp.mig_1793185083` | full | PASS | `grant_extra` ×3 (structural) + `by_design_unverified` ×3 (evidence) | **PASS** | `mo-invoice-quality-catalog-grants` |

## Per-unit

### b1-plans (PR #2342 @ `d5b4e00f`)

- `git diff --name-only` base…head: only `.migration/recon/u-plans/` inside `.migration/` — no `protected_files_tampered`.
- Independent re-run `result.json`: parity PASS; tiers 1–3 pass over the full keyed diff
  (Tenant One scope via the child's committed `mapping_spec_scoped.json`); verdict FAIL on
  tier 0 structural only — 3 `trigger_extra` on `subscriptions` (target 1/source 0 each),
  the known RO-catalog trigger-visibility false failure. `blocker_classes = [structural]`,
  exactly the classes `mo-plans-trigger-visibility` covers → PASS under `human_override`.
- Gates opened: `recon_pass` (result.json, parity PASS); `routine_parity` (3 proven / 0
  unproven / 0 failed — `sp_change_plan`, `trg_sub_no_uncancel`, `trg_subscriptions_hist`;
  golden == observed in each `runs/*.run.json`); `rerun_proof` (fresh `pass`, evolved
  `unsupported`, carried `passed: true`; rerun sources match the committed DDL/load set).
- Probes: 1 Tenant-One subscription each side, 0 scope-leak, 0 duplicate PKs, hist empty
  both sides (consistent), decimal extremes `499.00/49.00/0.055` equal, NULL `ends_on` 1=1,
  no empty-string ids.

### b1-quality (PR #2333 @ `91e8e816`)

- `git diff --name-only` base…head: only `.migration/recon/u-invoice-quality-pipeline/` — clean.
- Independent re-run `result.json` at depth `full`: parity PASS; verdict FAIL on
  `grant_extra` ×3 (all on service principal `bc8a2ef7-…`, the catalog-inherited-grant false
  failure in `structure.py:compare_grants`) + `by_design_unverified` ×3; `blocker_classes =
  [evidence, structural]`, exactly the classes `mo-invoice-quality-catalog-grants` covers →
  PASS under `human_override`. `grading` marks exactly the 3 objects the batch's
  `by_design_unverified` lists → no `grading_mismatch`.
- Gates opened: `expectations_evidence` (5/5 expectations fire as specced; independent
  violating-row recounts 37/0/0/0/50 == sink tag counts; two COMPLETED pipeline updates
  recorded); `rerun_proof` (fresh `pass`, evolved `pass`; source =
  `databricks/mig_1793185083/b1-quality/src/invoice_quality.py` as committed).
- Probes: independent source recount confirms 37 orphan `INVOICE_LINE` rows (==
  `invoice_line_quarantine` 37, all tagged `line_has_header` only);
  `customer_master_quarantine` 50 rows all tagged `cm_signup_dt_parseable`; estate totals
  150000/18750/25001 match the evidence's refreshed extract; 0 undeclared reject reasons;
  0 duplicate sink PKs.

## Findings

| Code | Location | Detail |
|---|---|---|
| `fanout_override_downgrade` | `migration-fanout/workflow.py:run_batch` (~line 1150) | 0.6.2 downgrades a FAIL-verdict batch before reading `merge_override`, skipping verify and making merge authority unproducible — the reason this verification is out-of-band |
| `grant_extra_false_failure` | `data-reconciliation/structure.py:compare_grants` | Catalog-inherited grants (SP `bc8a2ef7-…`, modify+select) counted as `grant_extra` structural blockers; known 0.6.2 false failure |
| `trigger_extra_false_failure` | `data-reconciliation/structure.py` trigger compare | Source RO catalog cannot see source triggers; target-side triggers counted as `trigger_extra` gaps on `subscriptions` |
| `child_depth_below_manifest` | batch b1-quality evidence | Child's committed recon ran `depth=threshold` vs manifest `verify_depth=full`; harmless because this run re-verifies at `full`, but the child's evidence undershoots the pin |

## Cost

`recon_cost` (sum of this verifier's `result.json['cost']`):
source 94 statements / 37 rows; target 84 statements / 37 rows; 39.3s elapsed.
Evidence: `u-plans/{result.json,report.md,recon.summary.md}`,
`u-invoice-quality-pipeline/{result.json,report.md,recon.summary.md}`, `probes.json`.
