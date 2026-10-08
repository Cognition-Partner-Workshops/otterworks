# 06 — Diff of this run against the prior record (UNT8: F1–F82, M1–M4, A2–A3)

**PR 1 (05_decisions.md):** https://github.com/Cognition-Partner-Workshops/otterworks/pull/1954 — opened 2026-10-08T13:50Z (timestamp read at 13:51:08Z, before any UNT8 prose was opened). Run branch `tp-run/mongodb-20261008T120222Z`; plugin `349cb2d17dccb246409e7750657e25843bf53be8` (unpatched); map-v3 sha256 `c158f8bb469d1e2733cfae5aa26e315d0ade4490f1164048ee161230c866dbd7`; tol-1; manifest_sha `ec9a01d04e88`; target `mmp_rt_b5_oracle`.

Prior record: `.migration/05_decisions.md` and `.migration/06_prior_run_diff.md` on `tp-run/mongodb-20261007T161014Z` (UNT8; plugin `353280fc`, map-v1.1, 24 tickets / ~425 ACU), read with `git show origin/tp-run/mongodb-20261007T161014Z:.migration/<file>` after PR 1 was open; not checked out, merged or copied. F1–F82 are the prior-prior findings as UNT8 carried them (F10 folded into F6, F80 into F78); M1–M4 and A2–A3 are UNT8's own §5b items named by the ticket.

## 0. Classification rule

By **this run's evidence only** — a committed artifact on the run branch, a ticket card (UNT9-1…13), a merged PR body (#1943–#1954), a `05_decisions.md` §e item (`e.n`), or the verifier report on `recon/wave-1-UNT9-7` (`vf n` = finding *n* in `.migration/recon/wave-1/verify-report.md`). Never by the prior run's status.

- **fixed** — this run shows the correct behaviour on the same path.
- **still present** — the same wrong or blind behaviour was observed here.
- **regressed** — this run shows a worse behaviour than the prior record.
- **not exercised** — this run did not drive the path (why is stated). The pinned SHA differs from UNT8's, so "code unchanged" is not claimed anywhere.

## 1. F1–F82

| id | prior finding (≤15 words) | class | this run's evidence |
|---|---|---|---|
| F1 | Harness venv ships no `recon` entry point | still present | e.2; UNT9-1 card; vf 11 (`~/.venvs/recon` had no entry point on two fresh hosts; `mongo-recon-harness 0.3.3` pip-installed from the pinned clone) |
| F2 | `test_migration_layout` fails from any cwd but a workspace root | not exercised | No harness test suite run this run; cards record `recon selftest` only (UNT9-1; vf 11 "PASS, 9 rules") |
| F3 | Harness tests need PyYAML the install never declares | not exercised | As F2 |
| F4 | dbx guard blocks every shell command inside the checkout | still present | e.1; `.migration/allowed_targets.json` `_compat_note` (`_check_python` rejects probe / census / recon scripts; `guard_mode: warn`); UNT9-1 card |
| F5 | Tolerance preset labelled `strict` is loosest | not exercised | `.migration/recon_tolerances.json` tol-1 written by hand (`numeric_abs_tol 0`, `aggregate_rel_tol 0`, `full_diff_row_threshold 100000`); no preset label consulted |
| F6 | Plugin pin not reproducible; venv installs not persisting | fixed | `349cb2d…` recorded in every `recon/wave-1/*/result.json`, every batch PR body (#1949–#1953), `05_decisions.md` header, verify-report header; install half remains F1 |
| F7 | `mongo_guard` compares against `origin/main` | not exercised | No card or artifact records a `mongo_guard` decision; only the dbx guard fired (UNT9-1) |
| F8 | `mongo_guard` misses Compass/driver writes | not exercised | No guarded write attempted; loaders ran under `guard_mode: warn` (allowed_targets.json) |
| F9 | `allowed_targets.json` schema mismatch; dbx guard fails closed | still present | e.1 (`catalogs` compat key + `guard_mode: warn` re-applied); UNT9-1 card |
| F10 | Duplicate of F6 | fixed | As F6 |
| F11 | `ALL_*` catalog views blind at read-only tier | not exercised | Source principal over-scoped (`connectivity.json` `privilege_excess`: CREATE TABLE/PROCEDURE/TRIGGER…); `census.json` inputs `plsql_objects 17`, `triggers 7` live |
| F12 | Probe allowlist path cwd-pinned | not exercised | Probe run from the run-branch root (UNT9-2 card command line); pin never hit |
| F13 | Block message recommends `--policy auto` | not exercised | UNT9-2 card records the BLOCKED verdict under `--policy online` and that the run continued; the hint text itself is not on the card |
| F14 | Live census returns 0 rows for 5 catalog queries | not exercised | Owner principal; `census.json` inputs all populated (`plsql_objects 17`, `triggers 7`, `sequences 5`, `scheduler_jobs 2`; `rowid_usage 0` is a true zero) |
| F15 | Live and DDL census disagree | not exercised | Live census only this run (`census.json` `mode live_catalog`; `pipeline_steps.txt` has no ddl-census step); no crosscheck document (lean run) |
| F16 | `ddl_census.py` misses anonymous blocks and MERGE | not exercised | As F15 |
| F17 | `reference_data_candidate` fires on an EAV value table | not exercised | `census.json` carries no `reference_data_candidate` trap at all; `entityAttrValue` is its own collection (units.json), per-trap census output not on UNT9-3 card |
| F18 | Profiler profiles FK-declared fanout only; pointer heuristic by name | still present | `data_profile.json`: `fanout` 13 = 13 FKs; 10 `pointer_resolve` stats bound by `*_ID` name (`INVOICE_LINE.TENANT_ID->TENANTS` resolve_rate 0.0) |
| F19 | `INVOICE_LINE.INVOICE_ID` bound to `INVOICES` not `INVOICE_HEADER` | fixed | `data_profile.json` `pointer_resolve:INVOICE_LINE.INVOICE_ID->INVOICE_HEADER` 37/1500 unresolved; vf 9 (37 planted orphans preserved verbatim) |
| F20 | EAV profiled per surrogate key, not per entity | still present | `data_profile.json` `eav:ENTITY_ATTR_VALUE` `max_attrs_per_entity 1`, `entities 70` (= one row per EAV_ID) |
| F21 | `text_shapes` conformance by shape, not by parse | still present | `text_shapes:CUSTOMER_MASTER.SIGNUP_DT` shapes `99-MAY-99`… all `status ok`; 41/201 unparseable by `strptime` (UNT9-12 card; vf 8; e.11) |
| F22 | `csv_elements` assumes comma, ignores empties, all-null is `ok` | still present | `csv_elements:CUSTOMER_MASTER_HIST.*` ×3 `status ok` with `max_elements null` on a 0-row table (`data_profile.json`) |
| F23 | `CODES` value domain never profiled against `*_CD` | fixed | `data_profile.json` 34 `code_resolve` stats; pipeline open question `code_lookup=12` surfaced (pipeline_steps.txt) |
| F24 | Tools assume fixture ≠ live source | still present | `fixtures/mmprt-mini.json` `method: synthetic`; every batch card "fixture is the live source, `--mode live`"; e.22; vf 3 |
| F25 | `row_estimate` NULL on tables with no statistics | still present | `census.json` `row_estimate` null on 20/20 tables; counts came from `fixtures/mmprt-mini.json.row_counts` instead (PR #1948) |
| F26 | Scanner reads only tables/relationships; trigger inventory not an input | still present | `access_patterns.json` 3 trigger rows for 7 census triggers; e.5 |
| F27 | SQL*Plus `/` not a segment separator; routines misattributed | fixed | `access_patterns.json` 51 `routine` attributions, `txn` anchored to package `file:line` on 44 rows; no misattribution recorded on UNT9-3/4 cards |
| F28 | Oracle trigger header never matched | fixed | 3 rows carry `trigger: {on, events}` (SUBSCRIPTIONS, USAGE_EVENTS, CUSTOMER_MASTER); residual F26 |
| F29 | `DBMS_SCHEDULER` jobs and ops scripts invisible | fixed | `access_patterns.json` 12 `invoked_by`, 12 `schedule_hint: daily`; `BYHOUR`/`enabled` still absent (0 occurrences); ops `.txt` still blind (e.7) |
| F30 | No call graph; every statement graded as if hot | fixed | `depth` on 14 patterns, `via` on 1 (`pkg_ow_util.log_msg` via `pkg_dunning.sp_schedule_dunning`); UNT9-3 card "depth 14 / via 1" |
| F31 | Multi-root scan emits absolute `source.file` paths | fixed | `access_patterns.json` 0 occurrences of `/home/`; evidence paths repo-relative |
| F32 | Deploy-script DML indistinguishable from runtime DML | still present | `deploy_script` on 2 candidates only (pipeline_steps.txt); 23 of 34 unfrequencied candidates were install/seed/upgrade scripts rejected by hand (UNT9-4 card) |
| F33 | PL/SQL semantics (loops, CURRENT OF, dynamic SQL) lost | fixed | `drives_loop` on 7 rows; dynamic calls `pkg_invoicing.sp_issue_invoice`, `pkg_ow_util.f_code_desc`, `pkg_plans.sp_change_plan` (pipeline_steps.txt) |
| F34 | `merge_rerun` drops hand corrections | not exercised | Single scan; no rerun recorded (UNT9-3/4 cards) |
| F35 | Dependency register has no contract; no tool reads it | not exercised | No register written (lean run: 05/06 are the only prose); preflight still warns `*.md` unread (e.13) |
| F36 | `join_edges` not byte-stable across reruns | not exercised | As F34 |
| F37 | Frequency vocabulary mismatches hot/warm/cold | not exercised | UNT9-4 card records 11 confirmed / 23 rejected; no translated vocabulary recorded |
| F38 | Horror tables have zero application access | still present | `INVOICE_HEADER`/`INVOICE_LINE` appear in 5 of 125 patterns, `no_access_evidence=10` open questions (pipeline_steps.txt); `ops/` yields nothing (e.7) |
| F39 | Trigger cascades invisible | fixed | 4 `cascades` rows → the SUBSCRIPTIONS and USAGE_EVENTS trigger rows (`access_patterns.json`); see A2 |
| F40 | `TRG_SUB_NO_UNCANCEL` silent coercion needs review | not exercised | No dependency register or trigger-body reading recorded this run; `trigger_business_logic=7` left as open questions dispositioned by `resolve` (UNT9-5) |
| F41 | Proposer has no notion of table-without-application-evidence | still present | `mapping_spec.json` proposes `invoiceHeader`/`invoiceLine` (F38 tables) as collections; `modeling.application_evidence` 2 recorded, `no_access_evidence=10` left to the human |
| F42 | Proposer would change decisions with true profile numbers | still present | `modeling.cardinality_default: assumed`, `basis: assumed=20 derived=3` (pipeline_steps.txt) although 10 `pointer_resolve` stats exist |
| F43 | `--ddl-census` traps never merged into proposer inputs | not exercised | No DDL census (F15); `modeling` has no `ddl_census` entry |
| F44 | `date_format_assumed` duplicates measured `text_shapes` | still present | `date_format_assumed=10` + `date_as_string=6` + `date_format_nonconforming=1` open questions (pipeline_steps.txt) beside 16 `text_shapes` stats; the HIST_DT one became e.8 |
| F45 | `FIXTURE_META` proposed; scope not a model input | still present | `mapping_spec.json` has `fixtureMeta` (19 collections), `modeling.excluded_tables 0`; excluded only downstream in `units.json` (PR #1948) |
| F46 | `pattern attribute` needs four ops; refuses surrogate-keyed EAV | not exercised | Both `pattern` decisions are `extended_reference` (design_decisions.json); `entityAttrValue` kept as its own collection |
| F47 | Orphans invisible to patcher; no remainder op | not exercised | `invoices.lines` embed 29/29 with 0 leftover children (PR #1952); the 37 `INVOICE_LINE` orphans are verbatim pointers (vf 9) |
| F48 | No op adds a field | fixed | `raw_field` adds `*Raw` fields (17 occurrences in mapping_spec.json; `signupDtRaw`, `histDtRaw`) |
| F49 | No raw+parsed text-date op | fixed | 11 `date_format` decisions with `raw_field` + `unparseable: null` (d-date-unparseable; map-v2/v3; PRs #1949, #1951) |
| F50 | No grouping/subdocument op for a 155-column table | still present | `mapping_spec.json` `customerMaster` 155 flat fields, 0 dotted targets |
| F51 | `csv_to_array` delimiter/trim not configurable | not exercised | 8 `csv_to_array` uses; element values not probed (no Atlas access on the record ticket; no batch card reports `"NULL"` tokens) |
| F52 | `reference` cannot add an edge | not exercised | No `reference` op this run (84 decisions: 69 resolve, 11 date_format, 2 pattern, 1 set_key, 1 note) |
| F53 | `extended_reference` cannot bind a constant join column | not exercised | Both `extended_reference` joins are on FK columns (`PLAN_ID = ID`, `TENANT_ID = ID`; 05 §b rows 11–12) |
| F54 | Vendored guidance cannot be cited | not exercised | All decision evidence paths are repo files (design_decisions.json); none attempted a plugin-guidance citation |
| F55 | `--check` ignores `unresolved` / open questions | not exercised | `--check` recorded only after all 30 unresolved were dispositioned (UNT9-5 card; `modeling.unresolved 0`); not run with open items |
| F56 | Embedding a child drops its `resolved_questions` | not exercised | Only embed is `invoices.lines`; child resolution counts not recorded |
| F57 | Preflight accepts a non-spec write target | not exercised | Every `write_targets` entry is a spec collection (units.json; preflight output in PR #1951) |
| F58 | Preflight never reads `connectivity.json` | not exercised | `source_access`/`target_access` declared in the off-repo wave spec (UNT9-6 card); whether preflight read `connectivity.json` is not recorded |
| F59 | No unit contract; wave spec kept out of `.migration/` | still present | `units.json` committed (PR #1948) but wave spec off-repo (`/home/ubuntu/wave-1.json`, PR #1951); no `.migration/waves/`; `manifest_sha` not reproducible from the ticket block (vf 12) |
| F60 | Harness has no source-schema option | not exercised | Owner principal; default schema sufficed (all 28 `result.json` PASS on key/count) |
| F61 | `Canonicalizer.equal` fails on unparseable source dates | fixed | `customerMaster.signupDt` null 41/201 with raw kept, Tier-3 PASS (vf 8) — only under `unparseable: null`; the family default `keep` still FAILs (e.11) |
| F62 | Attribute embed key uniqueness unchecked | not exercised | No `pattern attribute` (F46) |
| F63 | Recon salt unnamed; unsalted by default; fixture re-reads live | still present | e.16; vf 10 (`redaction_salted false` in all 28 `result.json`) |
| F64 | Batch worker cannot grade its own result | still present | e.19: `--grade` reads `origin/<PR branch>` and needs all 5 batches at once; manager graded per PR head (UNT9-12 card) |
| F65 | `date_format` silently ignores `unparseable` | fixed | `mapping_spec.json` canonicalization carries `unparseable: null` (42 occurrences) emitted by `model_patch` |
| F66 | `set_key` on an embed is refused | not exercised | Single `set_key` is on a root collection (design_decisions.json); no embed key set |
| F67 | Duplicate indexes undetected | not exercised | `modeling.dropped_indexes 1` recorded; no batch card reports a duplicate index created |
| F68 | Never-loaded collection indistinguishable from empty | still present | `customerMasterHist` absent on the target; harness result says `0 source rows` only — absence found by the verifier's probe (vf 7) |
| F69 | Orphan remainder ungradable | not exercised | No remainder collection; orphans graded as verbatim pointers by probe (vf 9) |
| F70 | Zero-row unit reports PASS and merge-eligible | fixed | `customer-master` `merge_eligible false` + `UNVERIFIED` warning in `result.json` (UNT9-12 card; vf 7); carried into §d |
| F71 | `child_where` re-pin narrows grading | not exercised | `child_where` 0 occurrences in mapping_spec.json |
| F72 | Scoped embed can never be merge-eligible | not exercised | As F71 |
| F73 | `subscriptionsHist` PASS on 0 rows hid `histDt` format defect | fixed | 6 rows graded; the defect surfaced as FAIL under map-v2 and was corrected (b.13 → map-v3; PR #1951; UNT9-10); new symptom e.8 |
| F74 | Fixture-first artifact overwritten by live run | not exercised | No fixture-mode run this run (every batch card: "fixture is the live source") |
| F75 | Loader-only fields invisible to harness | fixed | `*Raw` fields are mapped and graded Tier 3; vf 8 (`signupDtRaw` on all 201) |
| F76 | Committed evidence stale against wave pin | still present | e.18: pin moved map-v1→v2→v3 mid-wave; 6 merged units re-gated gate-only (PR #1951); `manifest_sha` 0939e0b61b54 → 5715dd929db2 → ec9a01d04e88 |
| F77 | Cross-unit references graded by nobody | still present | vf 9: 14 cross-unit checks done by hand probes; no harness tier |
| F78 | Verifier record coupled to grader pass set | not exercised | No refresh; companion defect e.21 / vf 4 (`validate_verify` admits only PASS/FAIL) |
| F79 | Refreshed result cannot retain original loading branch | not exercised | No result refreshed; re-gated results in PR #1951 overwrote in place on the same branch |
| F80 | Duplicate of F78 | not exercised | As F78 |
| F81 | Merge record cannot describe a decision-merged batch | not exercised | `preflight.py --merged` not recorded on any card; w1-b01 merged with `customer-master` `merge_eligible false` by manager decision (UNT9-12) |
| F82 | Merge contract knows only batch PRs | not exercised | Verifier evidence merged via `recon/wave-1-UNT9-7` without a merge record (vf 5) |

## 2. M1–M4, A2–A3 (UNT8 §5b items named by the ticket)

| id | prior finding (≤15 words) | class | this run's evidence |
|---|---|---|---|
| M1 | Proposer never emits `written_together` / `via_trigger` | still present | e.5; `mapping_spec.json` and `access_patterns.json` 0 occurrences of either; UNT9-3 card |
| M2 | Pointer target bound by `*_ID` suffix (`SUBSCRIPTIONS_HIST.ID` → wrong table) | still present | Binding still by suffix (F18); now surfaced as `pointer_target_suspect=2`, `pointer_unresolved=4` open questions (pipeline_steps.txt) and closed by hand `resolve` (UNT9-5) |
| M3 | Trigger classified by owning table, not by trigger body | fixed | Both `_HIST` collections carry `history_copy` in `mapping_spec.json` (0 `sequence_trigger_identity`); 7 `trigger_business_logic` questions left to the human instead of auto-classified |
| M4 | Proposer pins a date format at conformance 0.0 | still present | `SUBSCRIPTIONS_HIST.HIST_DT` measured `%Y%m%d` 0% conformance yet proposed as date (PR #1951 "seeded rows measured YYYYMMDD 0% conformance"); e.8 |
| A2 | INSERT credited with an `AFTER UPDATE` cascade | fixed | All 4 `cascades` rows are event-matched: 2 `UPDATE subscriptions` → SUBSCRIPTIONS `[update, delete]` trigger, 2 `INSERT INTO usage_events` → USAGE_EVENTS `[insert]` trigger (`access_patterns.json`) |
| A3 | Autonomous-transaction routine (`log_msg`) not distinguished | still present | `pkg_ow_util.log_msg` row `ap-779ce5b5b7` has an ordinary `txn` anchor (`01_pkg_util.sql:66:5`); `autonomous` 0 occurrences in `access_patterns.json` |

## 3. Class counts

| class | count | ids |
|---|---|---|
| fixed | 20 | F6 F10 F19 F23 F27 F28 F29 F30 F31 F33 F39 F48 F49 F61 F65 F70 F73 F75 M3 A2 |
| still present | 27 | F1 F4 F9 F18 F20 F21 F22 F24 F25 F26 F32 F38 F41 F42 F44 F45 F50 F59 F63 F64 F68 F76 F77 M1 M2 M4 A3 |
| regressed | 0 | — |
| not exercised | 41 | F2 F3 F5 F7 F8 F11 F12 F13 F14 F15 F16 F17 F34 F35 F36 F37 F40 F43 F46 F47 F51 F52 F53 F54 F55 F56 F57 F58 F60 F62 F66 F67 F69 F71 F72 F74 F78 F79 F80 F81 F82 |

88 rows (82 F + 4 M + 2 A). Counts verified by the script in §5. Against UNT8's own tally (30 fixed / 27 still / 0 regressed / 25 not exercised over F1–F82): F25, F32 and F44 went from fixed to still present on this run's evidence (no `--count-rows`, weaker deploy-script detection, assumed date formats carried into open questions); F30 went from still present to fixed (call-graph fields present); F2, F3, F13, F40, F46, F62 went to not exercised because the lean run never drove those paths. Nothing regressed.

## 4. New in this run — items with no F1–F82 / M / A counterpart

Same evidence rule. `e.n` = `05_decisions.md` §e row.

| this run | summary | nearest prior item (why not a counterpart) |
|---|---|---|
| e.3 | DSN principal cannot read `V$SQLAREA`/`V$SQLSTATS`; `--emit-sql` → fixture SYSTEM → `--from-results` leaves no provenance marker in `workload.json` | — (UNT8 had no workload export step) |
| e.6 | `known_incompatibilities` key absent from `data_profile.json` | UNT8 M11 was rows needing interpretation; here the key is missing |
| e.8 | Design `resolve` on a date question emits no `date_format`; `--check` does not flag it | F55 is unresolved items; this is a *resolved* item with no rule |
| e.9 | `--check` surfaces census / access-pattern / data-profile evidence one flag at a time | — |
| e.10 | `model_patch` applies ops in decision order; a `date_format` after a consuming `resolve` is refused in natural position | — |
| e.11 | Family default `unparseable: keep` can never PASS recon on planted garbage dates | F61/F65 were the missing option; this is the wrong default |
| e.12 | ≤5 units per batch and same-depth batches force 5 batch tickets for 13 units (13 > 12 tickets) | — |
| e.13 | Preflight warns about artifacts it never reads (`05_decisions.md`, `units.json`, `workload.json`, …) | F35 names `*.md` only |
| e.14 | Harness grades all 19 spec collections unless `--collections` is passed | — |
| e.15 | Harness CLI requires `--canonicalization`; ticket method omits it; `result.json` does not record which file was used | — (vf 6) |
| e.17 | Tier 4 never run: no `--ops`, no `ops/` under `.migration/` | UNT8 ran Tier-4 `custbill-ghost-lines` (its F69 row) |
| e.19 | `--grade` reads `origin/<PR branch>` — deleted at merge; verifier cannot reproduce `manifest_sha` from the ticket block | F64 is the worker side; this is the wave side (vf 12) |
| e.20 | `--verify` hard-codes `recon/wave-1`; three PASS batches "not evidence" because the grader reads another run's branch | UNT8 P5 reported the collision; this run shows the grader also *reads* the wrong branch (vf 5) |
| e.21 | `wave-verify` skill allows DRIFT-EXPLAINED; `validate_verify` admits only PASS/FAIL → `wave_verdict FAIL` for a wave with no defect | UNT8 P6 was about UNVERIFIED; here it is drift (vf 4) |
| e.22 | Fixture manifest pins row counts but not SYSDATE-stamped columns (`LOGGED_AT`, `HIST_DT`); independent re-verification on a fresh host can never PASS w1-b02 / `subscriptions` | F24/P4 are fixture≠live; this is value-level non-reproducibility (vf 1–3) |
| e.23 | `spec_diff vs pinned` exits 1 on a legitimate one-edge change | UNT8 C2 was `census_diff`; same shape, different tool |
| — | `connectivity.json` `blocked: true` on `privilege_excess` both sides, yet the run proceeds as `live`/`migration_cluster` with no override recorded (e.4) | UNT8 P2 is the same probe behaviour; carried as still present, listed here for the missing override field |

Not listed: items that are counterparts of a row above (e.1→F4/F9, e.2→F1, e.5→M1/F26, e.7→F29/F38, e.16→F63, e.18→F76).

## 5. Self-check of this file

```sh
python3 - <<'PY'
import re
L=open('.migration/06_prior_run_diff.md').read().splitlines()
rows=[l for l in L if re.match(r'\| (F\d+|M\d|A\d) \|',l)]
ids=[l.split('|')[1].strip() for l in rows]
assert ids==[f'F{i}' for i in range(1,83)]+['M1','M2','M3','M4','A2','A3'], ids
cls=[l.split('|')[3].strip() for l in rows]
assert set(cls)<={'fixed','still present','regressed','not exercised'}
assert all(len(l.split('|')[2].split())<=15 for l in rows), [l for l in rows if len(l.split('|')[2].split())>15]
from collections import Counter; c=Counter(cls); print(c)
tab={l.split('|')[1].strip():set(l.split('|')[3].split()) for l in L if re.match(r'\| (fixed|still present|regressed|not exercised) \|',l)}
for k,v in c.items(): assert len(tab[k])==v==int([l for l in L if l.startswith(f'| {k} |')][0].split('|')[2]), k
PY
```

Produced for ticket UNT9-8 (`s5.1-record`) on 2026-10-08; no Oracle or Atlas connection was opened; the legacy estate, the plugin clone and `.migration/05_decisions.md` were not touched by this PR.
