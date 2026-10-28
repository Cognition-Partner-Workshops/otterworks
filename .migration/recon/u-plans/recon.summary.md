# Recon summary: `u-plans` - **parity PASS, merge blocked (structural)**

- Blockers: structural: structural_gap, tier_failed
- Verdict: FAIL / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `ow-tp-map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `full`
- Generated: 2026-10-28T16:10:53.601675+00:00
- Cost: source 66 statements / 37 rows fetched; target 57 statements / 37 rows; 4.75s

## Routine parity: 3 proven, 0 unproven, 0 failed

- Structural checks: constraints=checked, triggers=checked, indexes=checked, sequences_identity=checked, grants=direct_only
- Rerun proof: fresh `pass`, evolved `unsupported` (no evolved record: pre-create the table in its previous committed shape (the prior proof's shape) and run again)

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 5 | FAIL (3) |
| 1 counts_through_mapping | 5 | PASS |
| 2 per_field_aggregates | 32 | PASS |
| 3 keyed_diffs | 37 | PASS |

Top findings (3 of 3; full list in result.json):
- T0 `subscriptions` trigger_extra: after delete row: target 1, source 0: writes the legacy app makes today behave differently
- T0 `subscriptions` trigger_extra: after update row: target 1, source 0: writes the legacy app makes today behave differently
- T0 `subscriptions` trigger_extra: before update row: target 1, source 0: writes the legacy app makes today behave differently

Full evidence: result.json, report.md (linked from the PR, not pasted).
