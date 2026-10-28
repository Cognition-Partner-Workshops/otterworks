# STOP E evidence pack — pipeline custbill

Run `tp-run/databricks-1793146609`, plugin dbx-migration-factory 0.6.1, tolerances `tol-20261027-v1` (family oracle, live). Parked per plan decision `custbill-wave-2-halt` (selected: park, user:dhrov.subramanian@cognition.ai). Nothing here approves STOP E — only the requester does.

## PROVEN — wave 1: custbill-feed

| | legacy | Databricks |
|---|---|---|
| Output | Oracle month-end extract (`oracle_custbill_extract.py`) + SFTP drop landing | `ow_tp.ow_tp_custbill.custbill_feed` — 18,750 rows |
| Recon | — | `dbx-recon --family oracle` parity PASS (`.migration/recon/custbill-feed/result.json`) |
| Verifier | — | independent verifier PASS (wave-1 close) |
| PR | — | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2305, merged `7fda6dae4` |

Merge authority: `mo-custbill-w1-structural` (human override, committed `authorizations.json`) covered the only blocker class — structural (Delta informational PK + platform-side target grants).

## UNPROVEN — wave 2: custbill-ldp

Deployed but NOT recon-proven. Numbers are the deployed pipeline's, labelled unproven:

| | legacy | Databricks |
|---|---|---|
| parsed records | `parsed/*.psv` | `parsed_records` 18,750 |
| rejects/quarantine | rejects file | `quarantine` 0 |
| finance totals | `finance_billing_*.csv` | `finance_billing_totals` 204 |

Why unproven — two gaps:
1. Spec shape: the committed `mapping_spec.json` grades the rejects-only quarantine table and the group-by rollup against the full root — no Oracle root exists for either, so the harness emits by-construction data blockers.
2. Plugin defect: recon's `_UC_PHYSICAL` excludes MATERIALIZED_VIEW/STREAMING_TABLE, so SDP materialized views are invisible to the rerun/structural checks.

PR https://github.com/Cognition-Partner-Workshops/otterworks/pull/2308 left open and unmerged; pipeline `ow_tp_custbill_ldp` and job stay PAUSED.

## Wave 3: custbill-job

Never launched (parked).

## Evidence

- Wave results/cards: `.migration/waves/wave-custbill-1.result.json`, `wave-custbill-1.card.md`, `wave-custbill-2.result.json`, `wave-custbill-2.card.md`
- Recon evidence: `.migration/recon/custbill-feed/` (result.json, routine_parity.json, rerun/)
- Plan decisions: `.migration/plan.yaml` (`custbill-merge-override-w1` accept, `custbill-wave-2-halt` park, `custbill-cutover-auth` hold)
- Authorizations: `.migration/authorizations.json` (`mo-custbill-w1-structural`)

No cutover performed; production consumers untouched; Oracle strictly read-only throughout.
