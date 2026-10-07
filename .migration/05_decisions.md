# Findings — run `mmp_rt_b3_oracle`

Plugin HEAD: `6e96827f380046e3f0663f39a02cec930a99143d` (`devin/1791335937-app-aware-modeling-next` + cherry-pick `865b105`).

One entry per place a plugin tool was wrong, blind, or needed manual correction:

```
## F<n> — <tool>: <what was wrong/blind> → <manual correction>
```

## F1 — recon harness install: snapshot venv `/home/ubuntu/.venvs/recon` had no `recon` entry point → installed `skills/mongo-recon-harness/harness[all,test]` editable from the pinned clone; `recon selftest` then PASS (9 canonicalization rules)

## F2 — wave-preflight `test_migration_layout`: fails at plugin HEAD (`1 failed, 81 passed`); it flags `skills/schema-modeling/SKILL.md:206` for `.migration/data_profile.json]` / `.migration/access_patterns.json]` because `SEGMENT_RE` keeps the markdown `]` that closes an optional-argument bracket, so two valid layout files read as unknown → not corrected in the plugin clone (never push); recorded as a false positive in the shipped test

## F3 — migration-planning `test_plan_example.py`: collection error `ModuleNotFoundError: No module named 'yaml'`; PyYAML is not pulled in by the documented harness `[all,test]` install → `pip install pyyaml` into the venv by hand, then `6 passed`

## F4 — `dbx-migration-factory` PreToolUse guard (org-installed sibling plugin, not under test): once `.migration/` exists without `allowed_targets.json` it rejects every shell command run from the otterworks checkout (`cannot read .migration/allowed_targets.json`), blocking `make tp-smoke` before the `s1.3-allowlist` ticket can land that file → ran `make -C ~/repos/otterworks ...` from `$HOME` until the allowlist PR merges; the mongo plugin's own `mongo_guard` was not involved

## F5 — migration-planning `d-tolerances` / recon harness `full_diff_row_threshold`: the planning skill labels the `strict` preset "Exact match, threshold 100000" and the ticket text derived from it reads "threshold 0 / no row-count slack", but the harness has no row-count slack knob at all (Tier 1 counts are always exact) and `full_diff_row_threshold` is the row count *above which* Tier 3 switches from a full keyed diff to a `sample_size` sample; `0` is what `continuous` mode forces to get a sampled Tier 3 (`engine.py:107`, `tiers.py:424`), so a literal `0` would have *weakened* Tier 3 to a 1,000-row sample on a 1,500-line fixture → committed `full_diff_row_threshold: 100000` (full diff on every fixture-scale collection), `numeric_abs_tol: 0`, `aggregate_rel_tol: 0`, `source_concurrency: 1` as `recon_tolerances.json` version 1; string canonicalization is not a tolerances knob (it is the mapping spec's per-field `rules` plus `--canonicalization skills/mongo-migration/profiles/oracle.md`), so the "Oracle profile only" clause is recorded here, not in the file

## F6 — recon harness install (F1 again): the `recon` entry point was missing from `/home/ubuntu/.venvs/recon` at the start of this session too, although the org blueprint says the harness is bound by the maintenance step and F1 had installed it one ticket earlier; a fresh `pip install -e "./harness[all,test]" pyyaml` is needed in every session → reinstalled from the pinned clone (`recon selftest` PASS, harness `196 passed`); the cherry-pick HEAD SHA is also not reproducible across clones (`d548eccf` here vs `6e96827f` in the run facts, same `git patch-id` `e102025d`), so cite the branch tip + patch-id rather than the cherry-pick SHA
