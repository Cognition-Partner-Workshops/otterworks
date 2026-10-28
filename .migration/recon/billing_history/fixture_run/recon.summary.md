# Recon summary: `billing_history` - **parity PASS, merge blocked (evidence, rerun_policy, structural)**

- Blockers: structural: structural_gap, tier_failed; evidence: routine_parity_missing, mode; rerun_policy: rerun_missing
- Verdict: FAIL / mode `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `sampled` / params `{'schema': 'OW_BILLING'}`
- Generated: 2026-10-28T01:48:36.568774+00:00
- Cost: source 506 statements / 304342 rows fetched; target 347 statements / 152107 rows; 174.683s

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `snapshot.customer_master` no row
- `snapshot.customer_master_hist` no row
- `snapshot.entity_attr_value` no row
- `snapshot.invoice_header` no row
- `snapshot.invoice_line` no row
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 5 | FAIL (19) |
| 1 counts_through_mapping | 5 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 152107 | PASS |

Top findings (5 of 19; full list in result.json):
- T0 `customer_master` primary_key_mismatch: source ('cust_id',) -> expected ('cust_id',), target ()
- T0 `customer_master` trigger_missing: after delete row: source 1, target 0
- T0 `customer_master` trigger_missing: after update row: source 1, target 0
- T0 `customer_master` trigger_missing: before insert row: source 1, target 0
- T0 `customer_master` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
