# Domain conversion contract

Legacy code is read-only. Inventory discovery is source-derived; do not remove an
object or alter its identity to make coverage pass. The foundation is not a claim
that a complete domain, full daily chain, or domain cron schedule is converted.

## Models and bronze inputs

- Use `lakehouse/dbt/models/{silver,gold}/<domain>/<lowercase_table>.sql`, where
  domain is `billing`, `documents`, `users`, or `audit`.
- Directory configuration supplies the domain tag, `<layer>_<domain>` schema and
  Delta location `.data/<NS>/delta/<layer>/<domain>/`. New models automatically
  join the domain's `dbt build --select tag:<domain>` task, including their tests.
- Keep names unique across the dbt project. Declare bronze sources in
  `dbt/models/sources.yml`; use `source()` and `ref()` rather than hardcoded paths.
  Bronze contains all dates: current-snapshot models must filter explicitly on
  `env_var('BUSINESS_DATE')`, not infer the newest partition or use wall-clock time.
- Read the complete legacy SQL/mapping and downstream consumers. Replicate types,
  nulls, collation, history, delete/update semantics and failures, or log explicit
  differences. Add dbt key/nullability and domain-specific invariant tests.
- Existing seed feeds already have readiness tasks and domain bronze nodes. For
  new landing feeds, extend the source metadata and source-derived inventory as
  needed, then add a `feed_sensor` with domain/table and make bronze depend on it.
  Do not silently treat a missing feed as an empty feed.

## Parity for every legacy output

Add `lakehouse/parity/specs/<domain>/<object>.yaml` with a unique `id`, stable
inventory `legacy_objects`, legacy/lakehouse readers, keys, explicit output
columns and justified normalization/tolerance. Use a spec per logical output,
not one successful account spec as evidence for an entire script or domain.
Use date-scoped files or a matching legacy snapshot for backfill parity: the
pilot PostgreSQL table is mutable and has no historical as-of reader.

Both sides must consume identical input files. Example fixture preparation and
checks (run from repository root; the legacy emulator remains running):

```sh
export NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-teradata-up NS="$LEGACY_NS" ROWS_PER_TABLE=2000 BUSINESS_DATE="$BUSINESS_DATE"
make sfx-lakehouse-up NS="$NS" ROWS_PER_TABLE=2000 BUSINESS_DATE="$BUSINESS_DATE"
make sfx-lakehouse-run NS="$NS" LEGACY_NS="$LEGACY_NS" \
  BUSINESS_DATE="$BUSINESS_DATE" SFX_LH_LANDING=warehouse/landing
make sfx-lakehouse-parity NS="$NS" LEGACY_NS="$LEGACY_NS" BUSINESS_DATE="$BUSINESS_DATE"
```

The graph includes its declared parity tasks; `sfx-lakehouse-parity` additionally
runs **all** specs, including newly added ones not yet wired into the graph.
`TD_PG_*` overrides are honored. Default emulator port derives from `LEGACY_NS`,
never lakehouse `NS`. Do not regenerate shared landing between the two engines.

## Coverage and assumptions

For every owned inventory ID, edit `coverage/coverage.yaml`:

- `converted`: actual lakehouse targets plus a covering parity spec with latest
  PASS JSON and current spec hash. Non-data orchestration/configuration may use
  `verification: test:lakehouse/tests/test_file.py::test_name` instead.
- `replaced_by_platform`: document the precise replaced responsibility and
  targets. Cron/runner replacements require a named verification test. Do not
  mark an entire script/stage/cron replaced when it also executes unported logic.
- `retired`: record why retirement is authorized; never use it to hide omissions.
- Otherwise keep `pending`. A scheduler stub or successful empty dbt selection
  does not convert a domain or output.

Record every ambiguity in `assumptions/assumptions.yaml`, using a new `A-NNN` ID,
affected inventory IDs, ambiguity, decision, rationale, low/med/high risk,
verification, accepted/open status and legacy source citations. Verification is
a spec ID, named `test:` reference, or `unverified: <specific reason>`. Link the
assumption from every affected coverage entry. Preserve open risks honestly.

Domain tickets must declare their ownership in
`lakehouse/coverage/domains/<domain>.yaml` as a `legacy_objects` list of stable
IDs, reviewed against inventory sources and consumers. This is an ownership
classification, **not** a replacement for automatic inventory discovery. Include
domain loaders, outputs, scripts, schedules and consumers; shared objects need
explicit responsibility and must not be excluded merely because they are hard.
Create that directory/file as part of the domain ticket; no complete domain
ownership or conversion is claimed by this foundation.

## Extending the declarative graph

Edit `orchestration/pipeline.yaml`; both executors consume exactly this file.
Every node declares `id`, `kind`, `depends_on`, `retries`,
`retry_delay_seconds`, and `legacy_objects` (empty if it replaces nothing yet).
Supported kinds:

| Kind | Additional fields |
|---|---|
| `feed_sensor` | `domain`, `table`, `timeout_seconds`, `poke_interval_seconds` |
| `bronze_ingest` | `domain` (all seed tables in that domain) |
| `dbt` | `domain`, `selector` (dbt `--select` expression) |
| `parity` | `spec` (one existing spec ID) |
| `export` | `command` (trusted argv list, not shell text) |
| `noop` | Only for explicitly unconverted placeholders |

Export argv supports `{python}`, `{business_date}`, `{landing}`, `{data_root}`.
Implement exports under `lakehouse/`, with retry-safe publication and parity.
Add each new output's parity node after the relevant dbt/export tasks. Add
explicit cross-domain edges when models or exports consume another domain;
tags do not infer these edges. Graph validation rejects cycles, unknown
dependencies, invalid task configuration and nonexistent legacy/spec IDs.

```sh
lakehouse/.venv/bin/python -m lakehouse.orchestration check
NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before \
  lakehouse/.venv/bin/python -m lakehouse.orchestration run \
  --business-date 20261109 --landing warehouse/landing
```

Local execution is topological, retries failed nodes, blocks their descendants
and continues independent branches. Airflow uses default `all_success` edges.
One task/run per DAG protects embedded Derby; local runs hold a namespace lock.
Do **not** mix manual/local runs and Airflow in the same namespace: Airflow's
per-task lock is not a whole-DAG lease across worker lifetimes.

## Dates, Airflow and backfills

The daily schedule is `@daily` UTC, not fixed 01:15. Business date is literally
**UTC logical date minus one calendar day**, not `data_interval_end - 1 day`.
For cron timetables Airflow labels interval starts, so a scheduled run may
process a date two days before its wall-clock trigger. To process 20261109 in
`airflow dags test`, pass logical date **2026-11-10T00:00:00+00:00**.
The seeded start logical date is 20261110; change it deliberately for older
scheduled backfills. Catchup is enabled and `max_active_runs=1`.

Producers must atomically publish complete files. Existence sensors accept an
empty valid file and do not check size stability or a batch manifest. There is
one-hour readiness timeout per attempt and one retry after ten seconds. The
hourly document-export DAG is paused, no-op and unconverted; its domain ticket
must implement the job and choose its actual cadence before unpausing it.

```sh
make sfx-lakehouse-airflow-test NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before \
  BUSINESS_DATE=20261109 SFX_LH_LANDING=warehouse/landing
```

This creates `.venv-airflow` using Python 3.12 and official Airflow 2.10.5
constraints, performs a DagBag/template test, migrates local SQLite metadata and
runs the actual daily DAG. Spark/dbt subprocesses still use `.venv`, not the
Airflow environment. All paths must be available on the same host. Metadata and
logs live under `.data/<NS>/airflow`. This is a local test setup, not a production
scheduler installation. No Docker Compose service is required or provided.

CI uses the same target with `SFX_LH_AF_DAG_TEST=0` for a DagBag/task/template-only
check, without PostgreSQL, Java or the Spark/dbt environment. The default remains
`1`, including the full local DAG execution. The runtime CI job connects directly
to a PostgreSQL 16 service using `TD_PG_HOST`/`TD_PG_PORT`, loads legacy inputs
through Python entry points and runs the graph on that same landing directory;
none of the lakehouse CI targets starts Docker or Compose.

## Definition of done

1. Ownership includes every domain output, control-flow object and consumer.
2. Global coverage/assumptions/graph validation has zero errors; no **owned**
   object remains pending. Global strict mode may still fail on other domains.
3. Every domain output has fresh PASS parity on shared inputs, plus empty/error
   and domain edge-case tests. No unreviewed normalization hides mismatches.
4. DAG tasks and dependencies are verified, including backfill/date behavior,
   readiness failure, retries and export idempotence. No placeholder is counted
   as a conversion. Open assumptions are explicitly reviewed/accepted as risks.
5. Tests are green; committed small JSON/Markdown evidence records actual
   provenance. Legacy code is unchanged.

Exact finishing commands, after creating the domain ownership file:

```sh
make sfx-lakehouse-coverage NS=sfx-d1110-after
DOMAIN=billing lakehouse/.venv/bin/python - <<'PY'
import os
from pathlib import Path
import yaml
from lakehouse.coverage.checker import entries
from lakehouse.coverage.inventory import discover
owned = yaml.safe_load(Path(f'lakehouse/coverage/domains/{os.environ["DOMAIN"]}.yaml').read_text())['legacy_objects']
assert owned and len(owned) == len(set(owned)), 'Ownership must be nonempty and unique'
assert set(owned) <= discover().keys(), 'Unknown ownership ID'
coverage = entries(Path('lakehouse/coverage/coverage.yaml'), 'objects')
pending = [identity for identity in owned if coverage[identity]['status'] == 'pending']
assert not pending, f'Pending owned objects: {pending}'
print(f'{os.environ["DOMAIN"]}: {len(owned)} owned objects, zero pending')
PY
make sfx-lakehouse-parity NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-lakehouse-test NS=sfx-d1110-after
make sfx-lakehouse-airflow-test NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before \
  BUSINESS_DATE=20261109 SFX_LH_LANDING=warehouse/landing
```

For final whole-estate acceptance additionally run
`lakehouse/.venv/bin/python -m lakehouse.coverage check --strict`.
