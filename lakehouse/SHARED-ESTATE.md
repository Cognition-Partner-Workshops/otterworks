# Shared legacy orchestration and libraries

All remaining platform-owned inventory responsibilities have named tests in
`tests/test_shared_estate.py`. They are platform replacements, not additional
business-data conversions. A-417–A-420 record their deliberate differences.

* The paused `lakehouse_daily` graph uses read-after-write dependencies, not the
  legacy total serial order. `tests/legacy_dependencies.py` derives stage lineage
  from the unchanged BTEQ scripts, SQL routines and views. Reports 10–11 do not
  read either billing table mutated by storage; monthly reports do. Independent
  branches may finish after an unrelated branch fails.
* `initialize` creates namespace-scoped Delta databases before ingestion. Feed
  readiness is still mandatory. Fixture generation is **not** a daily task:
  explicitly run `lakehouse_fixture_bootstrap` only against disposable landing
  data. It uses the same seeded generator as the legacy bootstrap, preserving
  `--rows` (default 200000), `--seed` (default 1110), and `--business-date`.
  Guide/Make smoke fixtures explicitly pass `ROWS_PER_TABLE=2000`.
* The host's 01:15 flock cron and Content's 02:15 scheduler are replaced by the
  paused UTC `@daily` catchup DAG, with logical-date-minus-one business dates,
  one active run/task, and the existing namespace lease. Cross-worker activation
  requires shared POSIX namespace storage or an external whole-run lease.
* Content APP_USER follows STG_APP_USER inside one ordered native operation.
  ROLE_GRANT and LOGIN_EVENT follow that operation. The documents operation waits
  for both APP_USER and ROLE_GRANT, then runs STG_DOCUMENT, DOCUMENT and DOC_SHARE
  in order. The disabled TEAM_MEMBER session is absent from scheduled tasks and
  scheduled users parity. After preparing daily bronze, run its standalone
  conversion and parity explicitly:

  ```sh
  NS=sfx-d1110-after lakehouse/.venv/bin/python -m lakehouse.orchestration run \
    --dag lakehouse_users_infa_team_manual --landing warehouse/landing \
    --business-date 20261109
  ```

  Full `parity --all` still includes TEAM_MEMBER. It must have a prepared manual
  output; scheduling the daily graph neither executes nor refreshes it.
* `runtime/informatica_settings.py` resolves global/workflow/session precedence
  from the native checked-in `informatica.par`; billing uses this adapter.
  Runtime business date supersedes the fixture LOAD_DATE. Native Delta transport
  uses namespace storage rather than distributing the Teradata credentials.
  Open A-403 remains the limitation for enabled archive history/sequence parity.
* Every Spark registry job has a converted node and PASS output parity. The
  unified graph runner replaces Docker `run.sh`; choose a job's DAG rather than
  JOB/SPARK_JOBS. Worker package imports replace common.zip and Scala assembly.
  Domain typed readers, strict missing-feed checks, overwrite snapshots and
  replay-aware billing append publication replace shared helper implementations.
  Spark event logs/history server settings are deliberately retired, not silently
  carried over. Task logs/states and parity evidence are the replacement.

## Full-DAG fixture replay

The legacy references must describe the same operational inputs as the graph:

* Set `AUDIT_SPARK_LANDING` to the prepared audit Spark fixture root (with
  `audit/AUDIT_EVENT/*.psv` and the other typed Spark feeds). This is not the
  Teradata landing directory; missing Spark feeds must still fail.
* Prepare `lakehouse.billing.consumer_reference` without `--clock-date` for a
  normal daily replay. Both sides then use BUSINESS_DATE plus one day (A-131).
* After preparing native Informatica inputs, run
  `lakehouse.billing.informatica_reference --business-date 20261109
  --landing warehouse/landing --replay-next-run` with the same namespace and
  legacy connection settings. The existing replay flag restores the captured
  starting sequence counter for the next graph run (A-120); it does not make
  production workflow retries idempotent or close the persistent-sequence risk.
* Reference preparation using BTEQ appends local emulator DBQL telemetry. Restore
  the historical CSV fixture with the existing DBQL loader before comparing the
  platform CSV-ingestion models, as described in `PLATFORM.md`.

These are local verification fixture operations, never automatic daily actions.
