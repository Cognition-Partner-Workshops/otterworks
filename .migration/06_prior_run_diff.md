# 06 — Diff of this run against the prior record (F1–F82)

Run branch `tp-run/mongodb-20261007T161014Z`; mapping `map-v1.1` (sha256 `3dc4060d…539b6`); target `mmp_rt_b4_oracle`.
Plugin under test: `Cognition-Partner-Workshops/mongo-migration-plugin` @ `353280fc837193a40ccc005cb62fb4ffaf8ac16f`, unpatched.

Prior record: `.migration/05_decisions.md` on `tp-run/mongodb-20261007T062215Z`, read with
`git show origin/tp-run/mongodb-20261007T062215Z:.migration/05_decisions.md` after §4b/§5b of this run's record were merged
(read gate). It was not checked out, merged, or copied. The prior record defines F1–F82 (80 distinct findings: F10 is folded
into F6, F80 into F78; prior tally 31 wrong / 42 blind / 7 manual corrections).

## 0. How each row was classified

Classification is by **this run's evidence only**, never by the prior PR's or ticket's status:

- **fixed** — this run shows the correct behaviour on the same path; the citation is this run's artifact that shows it.
- **still present** — the same wrong or blind behaviour was observed here; the citation is this run's artifact or §5b item.
- **newly regressed** — this run shows a worse behaviour the prior run did not record.
- **not exercised** — this run did not drive that path (why is stated); where useful, the plugin file:line at the pinned SHA
  is given to show the code is unchanged, which is not evidence of fixed.

Evidence base for this run: `.migration/05_decisions.md` §2, §3b, §4b, §5, §5b (items P*, C*, G*, A*, M*, H*), §6;
`.migration/01_census_crosscheck.md`, `02_dependency_register.md`, `03_access_scan_notes.md`, `03_access_review.md`,
`04_proposal_review.md`, `04_units.md`; `mapping_spec.json`, `design_decisions.json`, `access_patterns.json`,
`data_profile.json`, `data_profile_handcheck.json`, `census.json`, `fixtures/mmprt-mini.json`, `connectivity.json`;
`.migration/recon/*/{load,result}.json`, `recon/w1-b*.json`; and the verifier report
`git show origin/recon/wave-1-UNT8-18:.migration/recon/wave-1/verify-report.md` (cited as `verify-report` finding *n*).
Plugin citations are `~/mmp/<path>:<line>` at `353280fc`.

"Code unchanged" below means the same statement exists at the cited line at `353280fc`; the prior run tested a different
plugin HEAD, so this is support for *not exercised*, never a claim of *fixed* or *still present*.

## 1. F1–F82

| id | prior finding (≤15 words) | class | this run's evidence |
|---|---|---|---|
| F1 | Harness venv ships no `recon` entry point; `ls` skips preinstalled deps | still present | `~/.venvs/recon/bin/recon` absent on this VM; verifier had to build its own `~/.venvs/mmp` (verify-report "Independence caveat"); P8 |
| F2 | `test_migration_layout` fails from any cwd but a workspace root | still present | P8: 9 of 10 `cwd`-dependent tests fail from `/tmp` and `~/mmp`; `SKILL.md:162-163` |
| F3 | Harness tests need PyYAML the install never declares | still present | P8 (`ModuleNotFoundError: yaml` at collection); neither `~/.venvs/recon` nor `~/.venvs/poetry171` has `yaml` on this VM |
| F4 | dbx guard blocks every shell command inside the checkout | still present | P1: guard hard-blocked plugin scripts until `allowed_targets.json` gained the `catalogs` compat key and `guard_mode: warn` (`_compat_note`) |
| F5 | Tolerance preset labelled `strict` is loosest; no `0.0` label | not exercised | `recon_tolerances.json` tol-1 was written by hand at the required threshold; no artifact of this run consulted or recorded a preset label |
| F6 | Plugin pin not reproducible; venv installs not persisting | fixed | Pin reproducible: `353280fc` recorded in `fixtures/mmprt-mini.json` `producers`, every `recon/*/result.json`, batch results and verify-report. Install half remains as F1 |
| F7 | `mongo_guard` compares against `origin/main`, not the run branch | not exercised | No artifact records a mongo_guard decision or `MONGO_GUARD_BASE_REF`; code unchanged `hooks/mongo_guard.py:81-92` |
| F8 | `mongo_guard` misses Compass/driver writes; regex-only detection | not exercised | No guarded write attempted; P11 round-trip was a deliberate probe. Regex unchanged `hooks/mongo_guard.py:56-57` |
| F9 | `allowed_targets.json` schema mismatch; dbx guard fails closed | still present | P1: Mongo-shaped allowlist unreadable by dbx guard; `catalogs` compat entry added, guard downgraded to `warn` |
| F10 | Duplicate of F6 (pin reproducibility) | fixed | As F6 (prior record folds F10 into F6) |
| F11 | `ALL_*` catalog views blind to PL/SQL at read-only tier | not exercised | Source principal is schema owner (`connectivity.json` source `privilege_excess`; `load.json` `schema: OW_BILLING`); `census.json` live `plsql_objects` 17 |
| F12 | Probe allowlist path is cwd-pinned; no `--repo` option | not exercised | Probe ran from the run-branch root (P2); cwd pin never hit. `connectivity_probe.py:41/260` unchanged |
| F13 | Block message recommends `--policy auto`, inverting the policy | still present | P2: probe exited 1 under `--policy online` on `privilege_excess`, printing the `--policy auto` hint (`connectivity_probe.py:299`); the run did not follow it |
| F14 | Live census returns 0 rows for 5 catalog queries | not exercised | Owner principal: `census.json` inputs `plsql_objects 17`, `triggers 7`, `sequences 5`, `scheduler_jobs 2` all populated |
| F15 | Live and DDL census disagree on trigger/sequence contract | still present | C3; `01_census_crosscheck.md` §2 (both tool outputs, none silenced) |
| F16 | `ddl_census.py` misses anonymous blocks and MERGE | still present | C1; `01_census_crosscheck.md` §3 (unsupported syntax by file:line) |
| F17 | `reference_data_candidate` fires on an EAV value table | still present | C6 |
| F18 | Profiler profiles FK-declared fanout only; pointer heuristic by name | still present | G1 (13 fanout stats = 13 FKs; FK-less `*_ID` pointers unmeasured); `data_profile_handcheck.json` |
| F19 | `INVOICE_LINE.INVOICE_ID` pointer bound to `INVOICES` instead of `INVOICE_HEADER` | fixed | `data_profile.json` `pointer_resolve:INVOICE_LINE.INVOICE_ID->INVOICE_HEADER` 37/1500 unresolved; mapping `invoiceLine.invoiceId → invoiceHeader` (§2 #6). Residual G11 |
| F20 | EAV profiled per surrogate key, not per entity | still present | G3 (`eav_shape` "max 1 attr per entity" is per `EAV_ID`) |
| F21 | `text_shapes` conformance by shape, not by parse | still present | G4 (31 conformant by shape vs 41 unparseable by `strptime`; `customerMaster.signupDt` null 41/201) |
| F22 | `csv_elements` assumes comma, ignores empties, all-null is `ok` | still present | G5, G9, G10 (`csv_elements:CUSTOMER_MASTER_HIST.RELATED_ACCT_IDS` `status: ok`, values null) |
| F23 | `CODES` value domain never profiled against `*_CD` columns | fixed | `data_profile.json` 34 `code_resolve` stats join `*_CD` columns to `CODE_TYPE`; residual G6 (binding by naming convention) |
| F24 | Tools assume fixture ≠ live source; fixture is the live DB | still present | P4; `fixtures/mmprt-mini.json` `method: synthetic`; batch commits "fixture run first, scratch dir" against the same live source |
| F25 | `row_estimate` NULL on tables with no statistics | fixed | `catalog_census.py --count-rows` → `census.json` live counts; `fixtures/mmprt-mini.json` `row_counts_basis`; `01_census_crosscheck.md` §6 |
| F26 | Scanner reads only tables/relationships; emits empty inventory | still present | A1: 4 of 7 census triggers have no `access_patterns.json` row; census trigger inventory not an input |
| F27 | SQL*Plus `/` not a segment separator; routines misattributed | fixed | `03_access_scan_notes.md` §2 per-routine counts (48 `routine` attributions); §8 lists no misattribution; `_sql_file_segments` `access_scan.py:293` |
| F28 | Oracle trigger header never matched; trigger rows absent | fixed | `03_access_scan_notes.md` §3: every trigger row carries `trigger: {on, events}`; residual A1 (trigger-only writes undetected) |
| F29 | `DBMS_SCHEDULER` jobs and ops scripts invisible to scanner | fixed | `access_patterns.json` 11 `invoked_by`, `schedule_hint: daily` on job-driven routines (A11); residual A11/A14 (BYHOUR, `enabled=>FALSE`, `.txt/.sh` roots) |
| F30 | No call graph; every statement graded as if hot | still present | A3, A12 (`invoked_by` is flat; no routine→routine edges) |
| F31 | Multi-root scan emits absolute `source.file` paths | fixed | `03_access_review.md` §6: rerun with five `--root`s from the run-branch root, 0 absolute paths, byte-identical ids |
| F32 | Deploy-script DML indistinguishable from runtime DML | fixed | `access_patterns.json` `deploy_script: true` on 38 candidates; `03_access_review.md` "Deploy-script decisions"; A17 |
| F33 | PL/SQL semantics (loops, CURRENT OF, dynamic SQL) lost | fixed | `03_access_scan_notes.md` §5 `drives_loop`/`current_of`/`in_loop` rows; A13 dynamic SQL captured; residuals A6–A9 |
| F34 | `merge_rerun` drops hand corrections and pins | fixed | `03_access_review.md` §6: rerun kept 24 pinned rows, trigger/routine fields intact, `not_refound` empty |
| F35 | Dependency register has no contract; no tool reads it | still present | `02_dependency_register.md` is prose; `04_units.md` §5.1 preflight warning "`*.md` not read by any tool" |
| F36 | `join_edges` not byte-stable across reruns | fixed | `03_access_review.md` §6 "byte-identical" rerun; `access_scan.py:1272 merge_rerun` |
| F37 | Frequency vocabulary (`batch`/`read_hot`) mismatches tool's hot/warm/cold | not exercised | Reviewer graded directly in hot/warm/cold (`03_access_review.md` "Frequency basis"); no translated vocabulary asked for |
| F38 | Plan text names nonexistent access paths; horror tables have zero application access | still present | A17; `03_access_review.md` §3.17 (`INVOICE_HEADER`/`INVOICE_LINE` touched by 0 of 86 candidates) |
| F39 | Trigger cascades invisible; writes show no trigger side-effects | fixed | `access_patterns.json` 13 `cascades` rows; `03_access_scan_notes.md` §4; residual A2 (over-approximation) |
| F40 | Hand corrections need review; `TRG_SUB_NO_UNCANCEL` coerces silently, no RAISE | fixed | `02_dependency_register.md:85` reads the silent `:NEW.status_cd` coercion correctly; §3b rows 2/9 derive `CUST_SEQ_NO`/`CUST_NAME_UPPER` from the trigger. Wording slip in `03_access_scan_notes.md` §8.1 → post-diff note 2026-10-07 |
| F41 | Proposer has no notion of table-without-application-evidence | still present | M6; `04_proposal_review.md` §7 (`application_evidence` recorded, not consumed) |
| F42 | Proposer would change decisions with true profile numbers | still present | M6 (10 `pointer_only_no_fk` cardinalities `assumed` although `pointer_resolve` stats exist); §5 #7 |
| F43 | `--ddl-census` traps never merged into proposer inputs | fixed | `04_proposal_review.md` §5 `modeling.answered` entries with `kind: ddl_census`; residual M3 (trigger classified by table) |
| F44 | `date_format_assumed` duplicates measured `text_shapes` questions | fixed | `04_proposal_review.md` §4: 9 `date_format_assumed` all for empty-profile columns; `LAST_ACTIVITY_DT` (conformance 1.0) closed in `modeling.answered` |
| F45 | Scope/provenance not model inputs; `FIXTURE_META` proposed; absolute paths | fixed | `04_proposal_review.md` §1 `--exclude-table FIXTURE_META`; `design_decisions.json` evidence paths all repo-relative; residual P8 |
| F46 | `pattern attribute` needs four ops; refuses surrogate-keyed EAV | fixed | §2 #5: single `pattern attribute` compiled `customerMaster.attributes` with key `[ATTR_NAME, EAV_ID] → [k, eavId]` (`mapping_spec.json`) |
| F47 | Orphans invisible to patcher; no remainder op | not exercised | `INVOICE_LINE` is not embedded; `d-orphan-il-invoice` keeps the 37 pointers verbatim; proposer surfaced 37/1500 as `unenforced_pointer` (M10) |
| F48 | No op adds a field; `reference` on unknown edge is a no-op | fixed | §2 #1: `reference` on `SUBSCRIPTIONS_HIST.ID` created a new `decision.references` row; `date_format.raw_field` adds `*Raw` fields; residual H5 (derived flag) |
| F49 | No raw+parsed text-date op; `date_format` deletes resolutions | fixed | `mapping_spec.json` rule `date_string_to_date:dbyHMS-70a36e` with `raw_field`+`unparseable: null` (×16, d-dirty-dates); `modeling.resolved` 25 kept |
| F50 | No grouping/subdocument op for a 155-column table | still present | G7; `mapping_spec.json` `customerMaster` 159 flat fields, 0 dotted targets |
| F51 | `csv_to_array` delimiter/trim not configurable | still present | H1: rule params `{}`; `canon.py:115` default `,`; 4 arrays carry literal `"NULL"`/`"NONE"` |
| F52 | `reference` cannot add an edge; pattern labels double | fixed | §2 #1 (edge added by `reference`); `document_versioning` recorded as a note, no label doubling (`mapping_spec.json` `subscriptionsHist.decision`) |
| F53 | `extended_reference` cannot bind a constant join column | not exercised | §4: no `extended_reference` used in `map-v1.1` (d-codes-reference-data) |
| F54 | Vendored guidance (`reference/*.md`) cannot be cited | not exercised | `design_decisions.json` cites repo files only (`model_patch.py:1546` unchanged); no plugin-guidance citation attempted |
| F55 | `--check` ignores `unresolved`/open questions | fixed | §6.1: `model_patch.py --check` → `open items: 0 modeling.unresolved, 0 collection open_questions`, exit 0 |
| F56 | Embedding a child drops its `resolved_questions` | not exercised | `ENTITY_ATTR_VALUE` embedded by `pattern attribute`; this run's record does not count the child's resolutions before/after (§3.1 reports 42 resolved in total) |
| F57 | Preflight accepts a non-spec write target; grade fails later | not exercised | Every batch `write_targets` entry is a spec collection (`recon/*/load.json`); no remainder sink. `preflight.py:266 check_write_targets` unchanged |
| F58 | Preflight never reads `connectivity.json` | still present | P3 |
| F59 | No unit contract; wave spec kept out of `.migration/` | still present | Units as `.migration/ops/u*.json` + `04_units.md`; no `.migration/waves/` on the run branch (batch results carry `manifest_sha` only); `04_units.md` §5.1 layout warning |
| F60 | Harness has no source-schema option | not exercised | Source principal owns the schema (`load.json` `schema: OW_BILLING`); default schema sufficed |
| F61 | `Canonicalizer.equal` fails on unparseable source dates | fixed | H6: `customerMaster.signupDt` null 41/201 with `unparseable: null`, Tier-3 PASS; verify-report finding 5 |
| F62 | Attribute embed key uniqueness unchecked | fixed | Compiled key `[ATTR_NAME, EAV_ID]` is unique by construction; Tier-1 embeds 70/70; verify-report "Duplicate natural keys" clean |
| F63 | Recon cwd-pinned; salt unnamed, unsalted by default; fixture re-reads live | still present | P9: `redaction_salted: false` in all 20 `result.json`; verify-report finding 6; batch commits "fixture run first" against live |
| F64 | Batch worker cannot grade its own result | not exercised | `preflight.py --grade` not run in any batch PR; §4b downgrade derived from reading `preflight.py:334-372`; P6 |
| F65 | `date_format` silently ignores `unparseable` | fixed | `mapping_spec.json` canonicalization rule carries `unparseable: null`, emitted by the patcher (§6.1 "not edited by hand") |
| F66 | `set_key` on an embed is refused | fixed | `pattern attribute` emits embed key target `[k, eavId]` without hand edits (§6.1); no `set_key` needed |
| F67 | Duplicate indexes undetected | not exercised | `map-v1.1` has no duplicate index across 15 collections; `load.json` `indexes_created` distinct; `model_patch.py:1656` check exists |
| F68 | Never-loaded collection indistinguishable from empty; abort invisible | not exercised | All 10 loads completed (`load.json` per unit); only empty root is `u08` by source (0 rows), see F70 |
| F69 | Orphan remainder ungradable | not exercised | No remainder collection; orphans graded as verbatim pointers via Tier-4 `custbill-ghost-lines` (H5; verify-report finding 3) |
| F70 | Zero-row unit reports PASS and merge-eligible | fixed | §4b: `u08-customer-master-hist` `UNVERIFIED`, `merge_eligible: false`, warning text; verify-report finding 1. Residual H3 (tier rows still print PASS) |
| F71 | `child_where` re-pin narrows grading; remainder outside harness | not exercised | No `child_where` in any `map-v1.1` embed (`mapping_spec.json`) |
| F72 | Scoped embed can never be merge-eligible | not exercised | As F71; `tiers.py` scoped warning path never reached |
| F73 | `subscriptionsHist` PASS on 0 rows hid `histDt` format defect | fixed | `SUBSCRIPTIONS_HIST` 6 rows; §2 #3 format `%d-%b-%y %H:%M:%S`; H6 all 6 parse; `recon/u01-*/result.json` PASS; verify-report finding 8 |
| F74 | Fixture-first artifact overwritten by live run | still present | Harness `--out` keyed by unit; workers redirected fixture runs to a scratch dir (batch commits); only live `result.json` in tree |
| F75 | Loader-only fields invisible to harness | fixed | `*Raw` copies are mapped fields via `raw_field`, graded Tier 3; verify-report finding 5 (raw preserved 201/201); residual H5 |
| F76 | Committed evidence stale against wave pin | not exercised | Single pin `map-v1.1` throughout; all `result.json` and verify-report cite sha `3dc4060d…` |
| F77 | Cross-unit references graded by nobody | still present | verify-report "Cross-unit references" done by hand probes; finding 8; no harness tier |
| F78 | Verifier record coupled to grader pass set; cannot survive refresh | not exercised | No refresh happened; P6 shows the companion defect (`validate_verify` admits only PASS/FAIL) |
| F79 | Refreshed result cannot retain original loading branch | not exercised | No result refreshed; batch results carry `branch` of the loading PR only |
| F80 | Duplicate of F78 | not exercised | As F78 (prior record folds F80 into F78) |
| F81 | Merge record cannot describe a decision-merged batch | not exercised | `preflight.py --merged` not run; `d-unverified-batch-merge` (§4b) is such a merge, `validate_merge` (`preflight.py:468`) would reject it — code reading only |
| F82 | Merge contract knows only batch PRs | not exercised | As F81; `verify-report` merged via `recon/wave-1-UNT8-18` without a merge record (P5) |

## 2. Class counts

| class | count | ids |
|---|---|---|
| fixed | 30 | F6 F10 F19 F23 F25 F27 F28 F29 F31 F32 F33 F34 F36 F39 F40 F43 F44 F45 F46 F48 F49 F52 F55 F61 F62 F65 F66 F70 F73 F75 |
| still present | 27 | F1 F2 F3 F4 F9 F13 F15 F16 F17 F18 F20 F21 F22 F24 F26 F30 F35 F38 F41 F42 F50 F51 F58 F59 F63 F74 F77 |
| newly regressed | 0 | — |
| not exercised | 25 | F5 F7 F8 F11 F12 F14 F37 F47 F53 F54 F56 F57 F60 F64 F67 F68 F69 F71 F72 F76 F78 F79 F80 F81 F82 |

Total 82 rows (80 distinct findings + F10/F80 duplicates). Counts verified by the script in §4.

Reading: no F finding got *worse*. Of the 30 fixed, 11 are fixed only on the main path and leave a residual recorded as a
§5b item (F19→G11, F23→G6, F28→A1, F29→A11/A14, F39→A2, F43→M3, F45→P8, F48→H5, F70→H3, F75→H5, F44→M4 "new"). 17 of the
25 *not exercised* rows are harness/merge-contract paths that this run avoided by design (no scoped embed, no remainder
collection, no refresh, no `--grade`/`--merged`); they carry over as open.

## 3. New in this run — §2 / §5b items with no F1–F82 counterpart

| this run | summary | nearest F (why not a counterpart) |
|---|---|---|
| P2 | Probe skips its own target insert/delete round-trip when the role check fails first; `privilege_excess` on both sides | F13 covers the hint text only |
| P4 | `produced_by` is a free string; fixture manifest cannot declare that the fixture *is* the live source | F24 is the assumption, P4 the missing field |
| P5 | `preflight.py` hard-codes verifier branch `recon/wave-1`; collision forced evidence onto `recon/wave-1-UNT8-18` | — |
| P6 | `validate_verify` admits only PASS/FAIL; a wave with an UNVERIFIED unit has no clean verifier verdict | F78 is about refresh coupling |
| P7 | `model_patch.py` forces a version bump even for a notes-only change | — |
| P8 | 9 of 10 harness tests are cwd-dependent (beyond the two tests F2/F3 name) | F2/F3 cover two tests |
| P10 | Verifier and worker shared one host (`~/mmp`, same venv lineage, same fixture DB) | — |
| P11 | `_connectivity_probe` left as an empty collection in the target database | — |
| P12 | Fixture wrapper rerun doubles the audit log / persists across reruns | — |
| C2 | `census_diff.py` exits 1 on known differences; no accept-list | — |
| C4 | DDL census has no standalone-index bucket | — |
| C5 | Census input scope and cardinality are assumed, not declared | — |
| G2 | `history_copy` link `*_HIST → base` has no measuring stat | F18 is FK-only fanout; history links are a different trap |
| G7 | `repeating_group` slot utilisation unmeasured | F50 is the missing op; G7 the missing measurement |
| G8 | Polymorphic pointer (`AUDIT_LOG.ENTITY_ID`) unmeasured | — |
| G10 | Stats on empty tables return `status: ok` with null values | F22 names only `csv_elements` |
| A2 | INSERT credited with an `AFTER UPDATE` cascade (over-approximation) | F39 was invisibility; A2 is the opposite error |
| A3 | Autonomous-transaction routine (`AUDIT_LOG`) not distinguished (§2 #7) | — |
| A4 | Python `callfunc`/`callproc` callers not harvested | — |
| A5 | Non-FK `join_edges` (joins on `*_CD`) not emitted | — |
| A6 | `IS NULL` predicate graded as equality | — |
| A7 | Statement text truncated at 300 chars | — |
| A8 | `ROWNUM` / `FOR UPDATE` semantics dropped | — |
| A9 | `NOT EXISTS` wrapper collapsed to inner statement | — |
| A11 | `schedule_hint` drops `BYHOUR` and `enabled => FALSE` | F29 was total invisibility |
| A15 | Application SQL gets no `routine` attribution | — |
| A16 | Dead-code routine graded hot by the ticket rule | — |
| M1 | Proposer cannot express `written_together` / `via_trigger` (§2 #1) | — |
| M2 | Pointer target bound by `*_ID` suffix (`SUBSCRIPTIONS_HIST.ID` → wrong table) (§2 #1) | F19 is the profiler side |
| M3 | Trigger classified by owning table, not by trigger body (§2 #2) | — |
| M4 | Proposer pins a date format at conformance 0.0 with `date_format_basis: data_profile` (§2 #3) | F44 was duplicate questions; F73 the hidden default |
| M5 | `code_lookup` inferred from value overlap (§2 #4) | F23 is the profiler side |
| M7 | EAV proposed as separate collection "until ownership known" (§2 #5) | F46 is the patcher side |
| M8 | Operational documents (register, access review) are not proposer inputs | — |
| M9 | Record-only patterns (`document_versioning`) have no spec effect | — |
| M11 | `known_incompat` rows need manual interpretation (§3b) | — |
| H1 | `csv_to_array` keeps literal `"NULL"`/`"NONE"` tokens | F51 is delimiter/trim |
| H2 | Profile `missing` notes not surfaced in proposer output | — |
| H3 | Empty root prints PASS rows per tier while verdict is UNVERIFIED | F70 residual, new symptom |
| H7 | Pinned plugin ships no Oracle→Atlas loader; `scripts/tp_mongo/load_unit.py` (run branch) did the loading | — |

Not listed: items that are counterparts of an F row above (P1, P3, P9, C1, C3, C6, G1, G3–G6, G9, G11, A1, A10, A12–A14,
A17, M6, M10, H4–H6) and H4 (`type_mismatch`/`UNGRADED` not observed — a non-finding, not a defect).

## 4. Self-check of this file

```sh
python3 - <<'PY'
import re
rows=[l for l in open('.migration/06_prior_run_diff.md') if re.match(r'\| F\d+ \|',l)]
ids=[int(re.match(r'\| F(\d+) ',l).group(1)) for l in rows]
assert ids==list(range(1,83)), ids
cls=[l.split('|')[3].strip() for l in rows]
assert set(cls)<={'fixed','still present','newly regressed','not exercised'}
assert all(len(l.split('|')[2].split())<=15 for l in rows)
from collections import Counter; print(Counter(cls))
PY
```

Produced for ticket "Diff this run against the prior record F1-F82" on 2026-10-07; no Atlas or Oracle connection was
opened, `~/mmp` and the legacy estate were not touched, `.migration/05_decisions.md` §1–§5b were not edited.
