# Wave recon report — wave-invoicing-1

Verifier: independent re-run (wave-verify). Mode: `transactional` for all units
(Lakebase/operational track). Depth: `sampled` per manifest (Tier 1+2 + stratified Tier 3),
verifier seed `78123` (child ran `threshold`, seed `0` — verifier raised the depth to the
listed value). Tolerances `tol-20261027-v1` and `allowed_targets.json` taken from base
branch `tp-run/databricks-1793146609` (unchanged by the PR).

## Batch w1-b02 — PR #2289 (head 10aed76bd0f88e2d71a3e94b5d30f6c5c1f9cee6)

`.migration/` diff scope: clean — all changed paths sit inside
`.migration/recon/<unit_id>/`; no `protected_files_tampered`.

| Unit | Verifier parity | merge_eligible | Blocker classes | Verdict |
|---|---|---|---|---|
| pkg_ow_util | PASS | true | — | PASS |
| pkg_invoicing | PASS | true | — | PASS |
| pkg_plans | PASS | false | structural | PASS (override) |
| pkg_rating | PASS | false | structural | PASS (override) |
| pkg_dunning | PASS | false | structural | PASS (override) |

Batch verdict: **PASS**. `merge_authority` kind `human_override`, decision
`mo-invoicing-w1-structural` — the committed manifest's `merge_overrides` clears
`blocker_classes: ["structural"]` on exactly these five units, and `.migration/
authorizations.json` records the matching entry by dhrov.subramanian@cognition.ai.

## Structural blocker detail (forgiven by mo-invoicing-w1-structural)

Tier-7 `schema_parity` finds `trigger_extra` on the target only:

- pkg_plans: `subscriptions` — after delete row, after update row, before update row
  (target 1 / source 0).
- pkg_dunning: same three `subscriptions` triggers.
- pkg_rating: `usage_events` — before insert row (target 1 / source 0).

These are the converted equivalents of `trg_subscriptions_hist`, `trg_sub_no_uncancel` and
`trg_usage_events_check`: declared in the legacy DDL but never installed in the source
catalog (`ALL_TRIGGERS` empty), so the target deliberately carries more triggers than the
source. All blocker classes are `structural` — within the override's scope.

## Re-run coverage (Tier 3 keyed diffs, stratified sample, seed 78123)

The fixture is small, so the stratified sample covered 100% of each population:

- pkg_ow_util: codes 32/32, billing_audit_log 0/0
- pkg_invoicing: invoices 4/4, invoice_lines 4/4, credit_notes 5/5
- pkg_plans: subscriptions 70/70, plans 3/3, subscriptions_hist 0/0
- pkg_rating: usage_events 817/817, rating_periods 3/3, rating_results 3/3
- pkg_dunning: tenants 70/70, subscriptions 70/70, dunning_attempts 1/1, notifications 1/1

Tier 0 consistency windows, Tier 1 counts-through-mapping, Tier 2 aggregates, Tier 5
pk_set_diff and Tier 6 cdc_lag_ordering all passed on every unit; Tier 2 ran 0 checks
where the mapping has no numeric aggregates. Empty populations (subscriptions_hist,
billing_audit_log) matched empty on target. Cross-unit totals are consistent between
units that share tables (subscriptions 70/70 in both pkg_plans and pkg_dunning).

Routine parity: writer routines are `unproven` per the batch brief
(execute-posture `unproven-exceptions`, no EXECUTE grant) — expected; row parity is the
merge gate. Rerun proofs (`rerun_proof.json`) passed on all five units.

## Gate evidence check

`w1-recon` gate (kind `row_parity`): per-unit `w1-recon.report.json` files opened — all
five record `verdict: passed`, `parity: PASS`, mode transactional. Consistent with the
verifier's independent re-runs.

## Cost

Sum of `result.json['cost']` over verifier re-runs: source_statements 840,
source_rows_fetched 4070, target_statements 570, target_rows_fetched 2491,
elapsed_s 101.2.

## Findings

- Batch w1-b02 verifies PASS; pkg_plans, pkg_rating and pkg_dunning are merge-blocked on
  `structural` only (extra target triggers declared-but-never-installed on source) and are
  cleared by human override `mo-invoicing-w1-structural`.
- The child ran depth `threshold`; the manifest lists `sampled`, so the verifier raised
  the depth and re-ran at `sampled` with a different seed — parity still PASS on all units.
