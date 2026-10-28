# Recon summary: `codes` - **parity PASS, merge blocked (structural)**

- Blockers: structural: structural_gap, tier_failed
- Verdict: FAIL / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `ow-tp-map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `threshold`
- Generated: 2026-10-28T01:26:54.873657+00:00
- Cost: source 14 statements / 32 rows fetched; target 9 statements / 32 rows; 5.785s
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 1 | FAIL (3) |
| 1 counts_through_mapping | 1 | PASS |
| 2 per_field_aggregates | 3 | PASS |
| 3 keyed_diffs | 32 | PASS |

Top findings (3 of 3; full list in result.json):
- T0 `codes` primary_key_informational_only: target PK is informational, not enforced: duplicate keys would be accepted
- T0 `codes` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- T0 `codes` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
