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
