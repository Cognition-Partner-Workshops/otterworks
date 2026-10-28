# Recon summary: `scaffold` - **parity NOT_RUN, merge blocked (evidence, structural)**

- Blockers: structural: structural_gap, tier_failed; evidence: mode
- Verdict: FAIL / mode `structural`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `ow-tp-scaffold-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `threshold`
- Generated: 2026-10-28T10:25:31.629292+00:00
- Cost: source 113 statements / 0 rows fetched; target 99 statements / 0 rows; 55.515s
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 14 | FAIL (55) |

Top findings (5 of 55; full list in result.json):
- T0 `ow_tp.r1793176531_recon.legacy_codes` primary_key_informational_only: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- T0 `ow_tp.r1793176531_recon.legacy_codes` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- T0 `ow_tp.r1793176531_recon.legacy_codes` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- T0 `ow_tp.r1793176531_recon.legacy_tenants` primary_key_informational_only: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- T0 `ow_tp.r1793176531_recon.legacy_tenants` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
