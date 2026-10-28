# Recon summary: `billing_history` - **parity PASS, merge blocked (structural)**

- Blockers: structural: structural_gap, tier_failed
- Verdict: FAIL / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `sampled` / params `{'schema': 'OW_BILLING'}`
- Generated: 2026-10-28T02:15:49.785070+00:00
- Cost: source 506 statements / 304342 rows fetched; target 347 statements / 152107 rows; 339.685s

## Routine parity: 0 proven, 5 unproven, 0 failed

- `snapshot.customer_master` unproven: no committed run
- `snapshot.customer_master_hist` unproven: evidence .migration/recon/billing_history/routine_runs/snapshot_customer_master_hist.run.json is not a committed file
- `snapshot.entity_attr_value` unproven: evidence .migration/recon/billing_history/routine_runs/snapshot_entity_attr_value.run.json is not a committed file
- `snapshot.invoice_header` unproven: evidence .migration/recon/billing_history/routine_runs/snapshot_invoice_header.run.json is not a committed file
- `snapshot.invoice_line` unproven: no committed run
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only
- Rerun proof: fresh `pass`, evolved `unsupported` (evolved pre_shape equals the fresh shape: nothing evolved, so the run proves only what fresh proved)

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 5 | FAIL (15) |
| 1 counts_through_mapping | 5 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 152107 | PASS |

Top findings (5 of 15; full list in result.json):
- T0 `customer_master` primary_key_mismatch: source ('cust_id',) -> expected ('cust_id',), target ()
- T0 `customer_master` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- T0 `customer_master` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- T0 `customer_master_hist` primary_key_mismatch: source ('hist_id',) -> expected ('hist_id',), target ()
- T0 `customer_master_hist` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
