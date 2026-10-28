# Recon summary: `usage_rollup_scala` - **parity PASS, merge blocked (structural)**

- Blockers: structural: structural_gap, warnings
- Verdict: PASS / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `full`
- Generated: 2026-10-28T03:15:14.327645+00:00
- Cost: source 10 statements / 3 rows fetched; target 4 statements / 3 rows; 3.988s

## Routine parity: 0 proven, 2 unproven, 0 failed

- `analytics.ow_tp_analytics_usage_rollup` unproven: no committed run
- `analytics.usage_rollup_run` unproven: no committed run
- Structural checks: constraints=unsupported, triggers=unsupported, indexes=unsupported, sequences_identity=unsupported, grants=unsupported
- Rerun proof: fresh `pass`, evolved `pass`
- **WARNING: UNVERIFIED structural_parity: structure unavailable: usage_rollup: usage_rollup_output: information_schema.table_privileges read failed (ServerOperationError)**

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 0 | PASS |
| 1 counts_through_mapping | 1 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 3 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
