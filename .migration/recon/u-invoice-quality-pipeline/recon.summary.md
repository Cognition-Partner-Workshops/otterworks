# Recon summary: `u-invoice-quality-pipeline` - **parity PASS, merge blocked (evidence, structural)**

- Blockers: structural: structural_gap, tier_failed; evidence: by_design_unverified
- Verdict: FAIL / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Unverified by design: `customer_master_quarantine` unverified(by_design), `invoice_header_quarantine` unverified(by_design), `invoice_line_quarantine` unverified(by_design) (target rows <= root rows and structure graded; values not graded; merges only when the wave manifest's `by_design_unverified` declares the same objects)
- Mapping `ow-tp-map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `threshold`
- Generated: 2026-10-28T16:05:04.811255+00:00
- Cost: source 28 statements / 0 rows fetched; target 28 statements / 0 rows; 17.352s
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only
- Rerun proof: fresh `pass`, evolved `pass`

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 3 | FAIL (3) |
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 0 | PASS |

Top findings (3 of 3; full list in result.json):
- T0 `invoice_line_quarantine` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- T0 `invoice_header_quarantine` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- T0 `customer_master_quarantine` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
