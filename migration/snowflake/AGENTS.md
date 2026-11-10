# Migration session guardrails

These rules apply to every Devin session working under `migration/snowflake/`.

- `source/` is the legacy estate being migrated. Fix a divergence in the dbt model. The procedures, the generator, the SSIS packages and the replay harness stay as they are.
- `gate/manifest.yaml`, `gate/compare.py` and `gate/parity.py` are read-only. Changing keys, columns or comparison rules to make a unit pass is out of scope.
- A worker session owns one unit. It writes `target/dbt/models/marts/<unit>.sql` and that model's tests in `target/dbt/models/schema.yml`, and nothing else.
- A DIVERGE that's accepted needs an `Explanation:` line in `gate/out/ledger.md` saying why the Snowflake answer is right. Only the orchestrator writes explanations, and a person approves them in the PR.
- Every Snowflake object carries the run token. Work only inside the run's database (`OW_UBW_<TOKEN>`) and warehouse.
- Never print, commit or paste `SNOWFLAKE_PAT`, `SNOWFLAKE_PRIVATE_KEY`, `UBW_DBT_PRIVATE_KEY` or `UBW_SQL_PASSWORD`. Refer to them by name.
- Worker PRs go into the run branch. Devin never merges into `demo-snowflake-migration` or `main` and never approves its own PR.
