# Recon summary: `billing_history` - **parity PASS, merge blocked (structural)**

- Blockers: structural: structural_gap, warnings
- Verdict: PASS / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `sampled` / params `{'schema': 'OW_BILLING'}`
- Generated: 2026-10-28T01:32:09.199761+00:00
- Cost: source 506 statements / 304342 rows fetched; target 347 statements / 152107 rows; 366.952s

## Routine parity: 3 proven, 2 unproven, 0 failed

- `snapshot.customer_master` unproven: no committed run
- `snapshot.invoice_line` unproven: no committed run
- Structural checks: constraints=unsupported, triggers=unsupported, indexes=unsupported, sequences_identity=unsupported, grants=unsupported
- Rerun proof: fresh `pass`, evolved `unsupported` (evolved pre_shape equals the fresh shape: nothing evolved, so the run proves only what fresh proved)
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
