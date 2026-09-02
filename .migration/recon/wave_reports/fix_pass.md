# Fix pass — independent LIVE reconciliation (F-U8-1, F-X-1)

- Namespace: `mongo_205236` · target DB `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`)
- PR under review: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1457 (`tp-run/mongodb-20260901T205236Z--u8-fix` → `tp-run/mongodb-20260901T205236Z`)
- **attested_head: `7791a93e7033ba9ac8b40429d31f84127aec05a7`** (from `git ls-remote origin refs/pull/1457/head`, re-checked immediately before this report was written)
- Expected head at task start: `ba3b90346ff459906dfe569a8d069caf275b7962`. **The head moved during the session** (two new commits: `29f955ad` "counters-only seed is monotonic ($max upsert)…", `7791a93e` "regenerate counters-only load evidence"). The full pass below was **re-run from scratch against `7791a93e`**; the earlier `ba3b9034` grading (also PASS) is superseded and not relied upon.
- Reviewer session: independent of the fixing session; separate clone; harness `mongo-recon-harness` 0.2.1 (`recon selftest PASS: 9 canonicalization rules exercised`).
- Mapping `v1.0.1`, tolerances `v1`, canonicalization `v1`, seed `714559852`, `batch_no=85559852`, `source_ns=demo`; none of these were changed.
- Manifest SHA-256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` (unchanged).
- Secrets referenced by name only: `OW_BILLING_FIXTURE_DSN`, `MONGODB_ATLAS_URI`.

## Verdict: **PASS** — F-U8-1 and F-X-1 are closed at `7791a93e`.

## What was run (serial, source-load cap 1) — all at `7791a93e`, 2026-09-02 06:47Z–06:52Z

| Step | Command / action | Result | Evidence (`fix_pass_evidence/`) |
|---|---|---|---|
| Source pre-state | plain-SQL counts + `USER_SEQUENCES.LAST_NUMBER` + `BILLING_AUDIT_LOG` rows | RATING_PERIODS=3 RATING_RESULTS=3 INVOICES=3 INVOICE_LINES=2 CREDIT_NOTES=5 DUNNING_ATTEMPTS=1 NOTIFICATIONS=1 SUBSCRIPTIONS=69 SUBSCRIPTIONS_HIST=0 USAGE_EVENTS=814 TENANTS=69 PLANS=3 BILLING_AUDIT_LOG=1 CODES=32; sequences 2/125000/1/11001/1 | `source_pre.json` |
| U1 counters seed (one-off write authorised by decision row 19) | `scripts/tp_mongo/load_u1.py --counters-only` | 5 counters, `seeded == oracle_last_number` for all 5, `advanced_preserved=[]`, no drop/recreate (`$max` upsert) | `load_report.counters.json` |
| U8 load (replay clones reset) | `scripts/tp_mongo/load_u8.py` | all 12 `replay_u8_*` dropped+recreated; source_rows==inserted for every clone; `replay_u8_counters` seeded from `USER_SEQUENCES` (audit 2, hist 1) | `load_report.u8.json` |
| **U8 gate, VERBATIM** | `python .migration/recon_ext/recon_u8.py --unit U8 --mapping .migration/03_mapping_spec.json --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json --mode live --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo --out <dir>` | **PASS** — T1 8/8, T2 36/36, T3 902/902, **T4 6/6** (INVOICE-001…006 invoicing replays; `oracle_source_sha=0d326cad…d55`, `transcripts_match=true`) | `U8/gate/{result.json,recon.summary.md,tier4_provenance.json}`, `U8/gate.log` |
| U8 idempotency rerun | `load_u8.py` again + gate again | `result.json` identical modulo timestamps; load report identical modulo timestamps | `U8/gate_run2/`, `load_report.u8.run2.json`, `U8/idempotency.log` |
| U5 regression gate (T1–T3) | `recon run --unit U5 --family oracle …` (same flags, U5 mapping) | PASS — T1 11, T2 53, T3 902 | `U5/gate/` |
| U6 regression (reload + T1–T4) | `load_replay_u6.py` then `scripts/tp_mongo/recon_u6.py` | PASS — T1 14, T2 67, T3 1006, T4 5 | `U6/gate/`, `U6/load_report.json` |
| U7 regression (reload + T1–T4) | `load_u7.py` then `.migration/recon_ext/recon_u7.py …` (same flags) | PASS — T1 5, T2 23, T3 892, T4 8 | `U7/gate/`, `U7/load_report.json` |
| Independent probes (26) | `probes.py` (plain SQL vs Atlas; scratch `replay_fixprobe_*` only) | **26/26 ok, no flags** | `probes_current_head.json` |
| Source post-state | same plain SQL | **byte-identical to pre-state** — legacy untouched | `source_post.json` |
| Target fingerprint | count+sha of every golden/quarantine collection pre vs post | **every golden and quarantine collection sha-identical**; only `replay_*` clones changed | `target_pre.json`, `target_post.json` |
| `make tp-validate-recon FILE=fix_pass.recon.json` | schema validation of the assembled 41-check wrapper | `validated 1 recon file(s)` / PASS | `fix_pass.recon.json`, `build_wrapper.py` |
| `make tp-smoke` | at `7791a93e` | `tp-smoke: all checks passed` (41 passed) | `tp_smoke.log` |
| Unit tests (PR) | `pytest services/legacy-billing/tests` | 52 passed / 54 passed (rating/invoicing/util) | — |

Note: the raw harness `U8/gate/result.json` is the low-level harness object and does not carry the repo schema's top-level fields (`unverified_paths`, etc.); the schema-conformant wrapper `fix_pass.recon.json` is what `tp-validate-recon` graded, and it is assembled 1:1 from the raw results (see `build_wrapper.py`).

## Probe results (F-U8-1 / F-X-1 acceptance)

**F-U8-1 — `sp_issue_invoice` writes `invoice_id` on every embedded line**
- Golden `billing_invoices` and `replay_u6/u7/u8/u9_billing_invoices`: every `lines[]` element has non-null `invoice_id == parent._id == parent.id`. `replay_u8_billing_invoices` after the Tier-4 replays: 6 invoices / 17 lines / 0 bad (this is the path that exercises `sp_issue_invoice` rebuilds).
- Golden `(invoice_id, line_no)` set == Oracle `INVOICE_LINES` (2 == 2).
- Code: `services/legacy-billing/app/ow_billing/invoicing.py` rebuild now emits `"invoice_id": invoice_id` per line; `tests/test_invoicing.py` covers it.

**F-X-1 — one `counters` contract for every `log_msg` path, seeded from `USER_SEQUENCES.LAST_NUMBER`**
- `counters`: exactly one document per Oracle sequence (5): `seq_billing_audit_log=2, seq_customer_master=125000, seq_customer_master_hist=1, seq_entity_attr_value=11001, seq_subscriptions_hist=1` — each `== LAST_NUMBER`; shape `{_id, seq:Int64, source_sequence=_id.upper(), ns}`; no legacy `SEQ_BILLING_AUDIT_LOG`/`value` docs in golden or any clone.
- Static: `rating.log_msg` and `invoicing.log_msg` are thin delegates to `util.log_msg`; `plans`/`dunning` call `util.log_msg` directly.
- Dynamic (scratch clone, then dropped): util → rating → invoicing → util → rating → invoicing returned ids `[3,4,5,6,7,8]` from seed 2 — strictly monotonic, no collision, `_id==log_id`, Int64, modules in call order; counter advanced exactly +6; other 4 counters untouched; unseeded counter raises `LookupError` (loud). Cleanup verified; golden `billing_audit_log` still == Oracle (1 row).
- Clone audit logs after Tier-4 replays: `replay_u6` ids 1..4 (counter 4), `replay_u7` ids 1,3..10 (counter 10), `replay_u8` ids 1,3..16 (counter 16) — unique, increasing, `counters.seq == max(log_id)`.
- New at `7791a93e`: `load_u1.py --counters-only` uses `$max` upsert (`seed_counters_monotonic`) so a Mongo-advanced counter is never rewound; on this run `advanced_preserved=[]` (all counters were already == LAST_NUMBER).

## Unverified / carried forward (not graded as defects)
- Tier-4 source side is the recorded Oracle transcripts (source SHA verified live against `USER_SOURCE`), not live PL/SQL execution.
- F-U8-2 / F-U7-1 (ORA-02291 behaviour) unchanged; not re-probed here.
- `billing_audit_log` on U6/U7/U8 clones graded via probes (fixture row keyed-equal + id monotonicity) because the unit drivers exclude it from `GRADED_SOURCES`.
- Informational F-FIX-2: U6 replay seeder writes `LAST_NUMBER-1` whereas U1/U7/U8 write `LAST_NUMBER` (first Mongo-issued id differs by one; no collision possible).
- No HTTP route exercises `sp_issue_invoice`; Tier-4 and probes call the Python entrypoints directly.
- Concurrent `log_msg` writers not exercised (unit-tested only; `find_one_and_update` `$inc` is atomic).

## Merge recommendation
PASS at `7791a93e`; PR head unchanged between grading and report → eligible for merge into `tp-run/mongodb-20260901T205236Z` (fast-forward not possible: base has `419151d4`, `f5987c8a` not in PR; a merge commit is required). Production repoint is out of scope.
