# sfg1120 assessment evidence

The [manifest](manifest.json) and [wave plan](waves.md) use the source definitions
at `06096a70d67f54f88ce6c71c491093ac1253525d` and evidence gathered in local
namespace `sfx-sfg1120-before`. The older assessment in the parent directory
remains pinned to its own baseline.

## Observed and declared usage

- **Teradata DBQL.** The emulator loaded the branch's synthetic fixture.
  [Query history SQL](query_history.sql) joins `DBC.QryLogV` and
  `DBC.QryLogObjectsV` by query ID for August 12 through November 9, 2026,
  inclusive. There are 8,080 requests, including 16 failed requests.
  Across distinct object/principal/usage groups, there are 15,666 successful
  read references and 810 successful execute references. Counts can include more
  than one object per request. Writes and failed requests remain visible in the
  manifest. Daily-chain smoke traffic falls outside the historical window.
- **Coverage.** The 111 Teradata names and kinds agree across SQL definitions,
  `DBC.TablesV`, the emulator's relation catalog and its SPL/macro registry.
  PostgreSQL helper tables in `sfx_td` implement the emulator. Spark runs
  against a separate PostgreSQL fixture and its eight JDBC output tables
  appear as context, alongside 30 job definitions and their file inputs and
  outputs.
- **PowerCenter.** All three daily workflows succeeded with the full mapping
  selection. Eighteen enabled sessions succeeded. The two disabled sessions
  were skipped. The manifest records the workflow/session name, enabled state,
  local result, successful and failed runs in the DBQL window, and latest
  successful run from the full checked-in repository session log.
- **Spark.** The local master, two workers and history server started. The
  default batch submitted all 30 jobs, including `docs_folder_legacy_report`
  whose crontab entry is commented out. Twenty-nine jobs passed on the first
  submission. `file_object_binary_extract` initially failed to import
  `warehouse.run_config`. A retry with that module added to the generated
  Spark dependency ZIP passed and produced 200 rows. The checked-in baseline
  reconstructs from 30 historical Spark applications. A manual run proves
  the job can execute. Cron configuration determines whether the job provides
  an active scheduled reader.

## How to read the manifest

- `reads_from` shows SQL reads, lookups and stored-routine calls. A table with
  no SQL body lists its incoming data paths under `written_by`. Follow those
  writers to their source tables or landing feeds.
- `read_by` shows successful DBQL principals, declared registry consumers,
  dependent code and PowerCenter invocations. `writes_to` records destinations.
  A disabled session or inactive companion view can still appear as a declared
  edge on a retirement candidate.
- `active dependency` means a declared path reaches a successful DBQL reader,
  a registered contract, a daily BTEQ job, an enabled or observed PowerCenter
  mapping, or a scheduled Spark job. For example, audit reconciliation reads
  controls that DBQL showed only as write targets. Spark's `landing` and
  `register` helpers point to files. JDBC calls point to tables.
- `observed on first day only` preserves successful first-day observations for
  review. The first day is a time filter. It can include other usage alongside
  setup. Treat the nine candidate flags as evidence within this fixture;
  external workstations, dynamic SQL, and live production history are outside
  the observation scope. Lineage is object-level and follows qualified static
  references in the checked-in legacy SQL and exported jobs.

## Reproduce

Use the [repo's local-estate instructions](../../../.agents/skills/teradata-to-snowflake/SKILL.md)
with these settings. Pull the Compose images first if they are absent.

```sh
export RUN_TOKEN=sfx-sfg1120 NS=sfx-sfg1120-before
make sfx-informatica-up INFA_DB=teradata ROWS_PER_TABLE=200
make sfx-informatica-run INFA_DB=teradata MAPPINGS=all
make sfx-spark-up ROWS_PER_TABLE=200
make sfx-spark-run ROWS_PER_TABLE=200
```

For the binary job retry, add the package to the local generated dependency ZIP,
then submit the job directly. The Make job runner rebuilds the ZIP on invocation.

```sh
warehouse/.venv/bin/python - <<'PY'
import os
from zipfile import ZipFile

with ZipFile(f"etl/spark/.cache/{os.environ['NS']}/common.zip", "a") as bundle:
    bundle.writestr("warehouse/__init__.py", "")
    bundle.write("warehouse/run_config.py")
PY
docker compose -f docker-compose.spark.yml -p "$RUN_TOKEN-spark-$NS" exec -T spark-master \
  bash /opt/sfx/spark/submit/file_object_binary_extract.sh &&
  printf 'file_object_binary_extract\tOK\n' > /tmp/sfg1120-spark-retries.tsv
```

Capture the inventory while the databases are up. The command passes the
local Spark fixture password without printing it.

```sh
SFG_SPARK_DB_PASSWORD="$(docker compose -f docker-compose.spark.yml \
  -p "$RUN_TOKEN-spark-$NS" exec -T sfx-tdemu printenv POSTGRES_PASSWORD)" \
  warehouse/.venv/bin/python migration/dw-exit/sfg1120/capture.py \
  --source-ref 06096a70d67f54f88ce6c71c491093ac1253525d \
  --spark-retries /tmp/sfg1120-spark-retries.tsv
```

The HTML uses `lineage.body.html` with `manifest.json` as the data input to
Devin's `html_artifact_compile` tool.
