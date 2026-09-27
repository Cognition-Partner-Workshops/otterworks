# Recon summary: `lakebase_scaffold` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Merge authority: `harness` (human_override needs a merge_override row in .migration/06_decisions.md naming the unit)
- Mapping `map-20260927b-lakebase_scaffold-v1` / tolerances `tol-20260927b-v1` / seed `0` / depth `full` / params `{'ns': 'demo', 'batch_no': '85559852', 'admin_tenant_id': 'a0000000-0000-0000-0000-000000000001', 'fixture_tenant_id': '00000000-0000-0000-0000-000000000001'}`
- Generated: 2026-09-27T18:45:39.522192+00:00
- Cost: source 53 statements / 922 rows fetched; target 38 statements / 922 rows; 5.303s

## Routine parity: routine_parity_missing (no dependency analysis; commit .migration/units/lakebase_scaffold/dependencies.json, an empty `routines` list for a unit that writes nothing, or pass `--routine-dependencies`)
- Structural checks: constraints=checked, triggers=checked, indexes=checked, sequences_identity=checked, grants=direct_only
- Rerun proof: fresh `pass`, evolved `pass`

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 4 | FAIL (5) |
| 1 counts_through_mapping | 4 | PASS |
| 2 per_field_aggregates | 19 | PASS |
| 3 keyed_diffs | 922 | PASS |

Top findings (5 of 5; full list in result.json):
- T0 `codes` grant_extra: target grant dhrov.subramanian@cognition.ai (delete,insert,references,select,trigger,truncate,update) has no source counterpart
- T0 `plans` grant_extra: target grant dhrov.subramanian@cognition.ai (delete,insert,references,select,trigger,truncate,update) has no source counterpart
- T0 `tenants` grant_extra: target grant dhrov.subramanian@cognition.ai (delete,insert,references,select,trigger,truncate,update) has no source counterpart
- T0 `usage_events` trigger_missing: before insert row: source 1, target 0
- T0 `usage_events` grant_extra: target grant dhrov.subramanian@cognition.ai (delete,insert,references,select,trigger,truncate,update) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
