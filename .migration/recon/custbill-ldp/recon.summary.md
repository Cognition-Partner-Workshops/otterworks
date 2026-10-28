# Recon summary: `custbill-ldp` - **parity FAIL, merge blocked (data, evidence, rerun_policy, structural)**

- Blockers: structural: structural_gap, tier_failed; data: tier_failed; evidence: routine_parity_missing; rerun_policy: rerun_missing
- Verdict: FAIL / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `full`
- Generated: 2026-10-28T02:54:16.112255+00:00
- Cost: source 28 statements / 0 rows fetched; target 18 statements / 0 rows; 10.029s

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `custbill.ow_tp_custbill_ldp` no row
- `custbill.parse_custbill_fixedwidth` no row
- `custbill.finance_excel_report` no row
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 3 | FAIL (11) |
| 1 counts_through_mapping | 3 | FAIL (2) |

Top findings (5 of 13; full list in result.json):
- T0 `parsed_records` primary_key_mismatch: source ('invoice_id',) -> expected ('invoice_id',), target ()
- T0 `parsed_records` not_null_missing: source NOT NULL invoice_id -> target invoice_id is nullable
- T0 `parsed_records` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- T0 `parsed_records` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- T0 `quarantine` primary_key_mismatch: source ('invoice_id',) -> expected ('invoice_id',), target ()

Full evidence: result.json, report.md (linked from the PR, not pasted).
