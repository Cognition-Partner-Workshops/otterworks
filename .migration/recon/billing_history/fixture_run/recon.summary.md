# Recon summary: `billing_history` - **parity PASS, merge blocked (evidence, rerun_policy, structural)**

- Blockers: structural: structural_gap, warnings; evidence: routine_parity_missing, mode; rerun_policy: rerun_missing
- Verdict: PASS / mode `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `sampled`
- Generated: 2026-10-28T01:12:29.506585+00:00
- Cost: source 506 statements / 304342 rows fetched; target 347 statements / 152107 rows; 190.508s

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `snapshot.customer_master` no row
- `snapshot.customer_master_hist` no row
- `snapshot.entity_attr_value` no row
- `snapshot.invoice_header` no row
- `snapshot.invoice_line` no row
- Structural checks: constraints=unsupported, triggers=unsupported, indexes=unsupported, sequences_identity=unsupported, grants=unsupported
- **WARNING: UNVERIFIED structural_parity: structure unavailable: customer_master: customer_master: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: customer_master_hist: customer_master_hist: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: entity_attr_value: entity_attr_value: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: invoice_header: invoice_header: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: invoice_line: invoice_line: information_schema.table_privileges read failed (ServerOperationError)**

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 0 | PASS |
| 1 counts_through_mapping | 5 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 152107 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
