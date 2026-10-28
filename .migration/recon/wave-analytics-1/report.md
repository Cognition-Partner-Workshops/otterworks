# Wave recon report — wave-analytics-1 (independent verification)

Verifier: independent wave-verify session. Source and target read-only. Evidence re-run live; the PR's pasted evidence was not trusted.

## Batch a02 — unit `analytics_daily` (PR #2304)

- Head verified: `8ad29795498a7fc1e52b3230180c10d02d87f4a0` on `devin/1793154552-wave1-a02-analytics-daily`, base `tp-run/databricks-1793146609`.
- Mode: `live` (same as the child's merge-evidence mode). Depth: `full` (keyed full diff), as listed for this batch — not lowered. Seed: `7` (child used `0`).
- Tolerances `recon_tolerances.json` (`tol-20261027-v1`) and `allowed_targets.json` read from the base branch; confirmed byte-identical to the PR head versions — the child did not loosen a tolerance.
- `.migration/` footprint: `git diff --name-only` between base and PR head touches only `.migration/recon/analytics_daily/` paths — no `protected_files_tampered`.
- Re-run result (`result.json`): `parity=PASS`, `merge_eligible=false`, `blocker_classes=["structural"]`, `merge_block_reasons=["structural_gap","tier_failed"]` — matches the child's verdict.
  - Tier 0 structural deltas (class `structural` only): informational PK + `NOT NULL report_date` on target `analytics_daily_summary` not present on source; target `s3_key` `NOT NULL` on `analytics_daily_report`; grant lists differ by principal id (source grants `d9d1c4ec-…` all_privileges/select; target grants other SP ids).
  - Row tiers: keyed full diff clean — `analytics_daily_summary` keyed on `report_date`, `analytics_daily_report` keyed on `s3_key`; 2/2 rows matched on each side; no missing, extra, or value-drift rows.
  - Routine parity: 2 writers unproven (`analytics.ow_tp_analytics_daily`, `analytics.analytics_daily_run` — no committed run), same as the child's run.
  - Rerun posture `required`: committed `rerun_proof.json` validated — source digest matches the committed `ensure_objects.sql` and `run_analytics_daily.sql`; fresh and evolved legs pass.
- Merge authority: `human_override` decision `mo-analytics-w1-structural` (manifest `merge_overrides`, blocker_classes `["structural"]`, units `["usage_rollup_scala","analytics_daily"]`). Per the verifier rule the unit is marked PASS on a PASS verdict even though `merge_eligible=false`; the structural class is exactly the class the override clears.
- Gate `analytics_daily-recon` (kind `row_parity`, status `passed`): evidence `.migration/recon/analytics_daily/report.md` opened and shows the keyed-diff PASS with 2 rows per side — the evidence shows what the gate kind requires.
- Adversarial boundaries at full depth: keyed full diff covers empty/all-null, duplicate keys, and value drift by construction (every row compared); late arrivals and deletes would surface as row presence diffs — none present. Only 2 rows on each side exist in the live fixture, so skew/decimal/Unicode boundary material is thin; noted, not a blocker for this batch.
- Harness note: the plugin harness's `sql.connect(oauth_client_id/oauth_client_secret)` path hangs headless on connector 4.8 (interactive U2M). The run used a local copy of the harness with `_databricks_connect` pointed at the documented `access_token=_databricks_bearer()` path (SDK `Config().authenticate()` → oauth-m2m client-credentials as the doctor-verified service principal `d9d1c4ec-…`) — the same workaround the child recorded in `skill_feedback`. `t.owner` → `t.table_owner` (a plugin column-name bug in `information_schema.tables`) applied identically. No identity, endpoint, or catalog changed; the `dbx-recon` guard blocks on env-var reassignment were not routed around — the binary path was not invoked with modified environment.
- Cost of this verifier run: `{"source_statements": 20, "source_rows_fetched": 2, "target_statements": 18, "target_rows_fetched": 2, "elapsed_s": 12.14}`.

## Verdict

- `a02` (analytics_daily): **PASS** — parity PASS re-verified live at full depth; only structural blockers remain, cleared by `mo-analytics-w1-structural`.
- Wave verdict: **PASS**.
