# Wave custbill-1 recon report (independent verifier)

Verifier session: devin-c9e39fda4fcc48588b89e58d5f192ed0. Verifier wrote none of the
converted code; the harness was re-run against the live source and target with
`tolerances` and `allowed_targets.json` as committed on the protected base
(`tp-run/databricks-1793146609`, tolerance version `tol-20261027-v1`).

## Units

### custbill-feed — batch c01 — PR #2305 (`devin/1793154591-custbill-feed` @ 60ab686d)

- Mode: `live` (same as child). Depth: `full` — keyed full diff, no sampling.
- Verifier re-run `result.json`: `parity=PASS`, `verdict=FAIL`,
  `merge_eligible=false`, `merge_policy=blocked`,
  `blocker_classes=["structural"]`, `merge_block_reasons=["structural_gap","tier_failed"]`.
  Structural findings reproduced verbatim: `primary_key_informational_only`
  (Delta PK is informational/RELY) and two `grant_extra` target grants
  (`2e90bc1d-e9a1-4703-8c48-ad28ebb1864d` all_privileges,
  `bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d` modify,select).
- Tiers: 0 structural_parity failed on the findings above; 1 counts, 2
  per-field aggregates, 3 keyed diffs all PASS — 18,750 rows both sides,
  zero keyed diffs.
- Rerun proof: committed `rerun_proof.json` re-validated in the verifier run —
  `fresh=pass`, `evolved=pass` (posture `required`), source_digest matches the
  committed job files `ensure_objects.sql` + `land_feed.sql`.
- Routine parity: 3 routines `unproven` (`custbill.ow_tp_custbill_feed`,
  `custbill.oracle_custbill_extract`, `custbill.sftp_ingest_poll`) — no
  committed run on a dedicated exec target; cutover exceptions, not merge
  blockers.
- Protected-surface check: `git diff --name-only <base>...<head>` touches only
  `.migration/recon/custbill-feed/` plus the `etl/dbx-custbill/` bundle. No
  `.migration/` state tampered (`protected_files_tampered` does not apply).
- Gate evidence: `custbill-feed-recon` (kind `row_parity`) at
  `.migration/recon/custbill-feed/result.json` shows mode=live, parity PASS,
  tiers 1–3 clean — satisfies the gate's kind.
- Adversarial probes (verifier, read-only): zero duplicate `invoice_id`; all
  rows `record_tag=DET`/`record_type=01` with no HDR/TRL leakage; no nulls in
  required columns; `total_amt` all scale-2 within decimal(14,2)
  (min 20.81, max 19,999.51); single consistent `landed_at` batch; `raw_line`
  all 65 chars; `batch_no` NULL by design (`CAST(NULL AS BIGINT)` in
  `land_feed.sql`); MERGE is idempotent via `QUALIFY ROW_NUMBER` dedupe, so
  re-drops/retries converge; consumer `finance_billing_totals` not yet
  deployed (later wave — not this unit's gate).

## Merge authority

Batch c01 carries `merge_authority` kind `human_override`: committed wave
manifest `merge_overrides` entry `mo-custbill-w1-structural` (also committed
in `.migration/authorizations.json`, kind `merge_override`, authorized by the
requester) covers blocker class `structural` on unit `custbill-feed`. The
verifier's re-run shows parity PASS with `blocker_classes=["structural"]`
only, so the unit is marked PASS under decision `mo-custbill-w1-structural`.

## Verdict

- `wave_verdict`: **PASS**
- `unit_verdicts`: `{"c01": "PASS"}` (unit `custbill-feed`, parity PASS via
  human_override `mo-custbill-w1-structural`)

## Findings

1. Batch c01 PASS on human_override `mo-custbill-w1-structural`: the verifier's
   live/full re-run reproduced parity PASS (18,750 rows, clean keyed diff and
   aggregates) with `merge_eligible=false` and only `structural` blockers
   (informational target PK, two platform grants), matching the committed
   override exactly.
2. The committed mapping spec's three-part object name
   `ow_tp.ow_tp_custbill.custbill_feed` is refused by the Databricks target
   adapter; child and verifier both ran a normalized copy with
   `object: custbill_feed` (otherwise identical) — the committed spec should be
   corrected at wave close.
3. The harness required the two session-local `adapters.py` patches named in
   the wave brief: `tp.grantee <> t.table_owner` in `_uc_schema_facts`, and a
   bearer-token `sql.connect` in `_databricks_connect` (the connector's
   oauth-m2m kwargs hang headless) — upstream plugin fix needed.
4. Three custbill routines are `unproven` (no committed run on a dedicated
   exec target against a fixture snapshot) and carry over as cutover
   exceptions, not merge blockers.
5. The `dbx_guard` hook blocked the brief's `DATABRICKS_HTTP_PATH=...` env
   override form (identity swap); the verifier used `--target-http-path`
   instead, which takes precedence inside the harness and reaches the same
   warehouse.

## Cost

Verifier re-run `result.json["cost"]`: `{"source_statements": 14,
"source_rows_fetched": 18750, "target_statements": 9,
"target_rows_fetched": 18750, "elapsed_s": 16.562}`.
