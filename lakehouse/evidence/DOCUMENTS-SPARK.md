# Documents Spark first batch

Scope: seven documents-only Spark jobs, their submit wrappers and individual
cron inventory IDs: **21 IDs converted**. The 97-object documents ownership
list already contains these IDs and is unchanged. Later documents jobs and all
integration-owned objects remain pending. No legacy source, submit script,
shared Spark library/configuration, or cron file was edited.

## Independent shared-input execution

The deterministic fixture lives at `warehouse/landing/spark/20261109`, not in
the incompatible Teradata/Informatica feed directories. Both engines read those
exact files; the legacy container receives a read-only mount at `/opt/landing`.
The generator produces 68 documents, 69 file objects, 69 shares, 68 tags,
68 search logs, 20 users and 10 folders. It includes null aggregate inputs,
duplicate recipients, an empty folder, quoted delimiters, Unicode/whitespace
tags, absent/Unicode/first-match actions, and negative/boundary document IDs.

[Provenance](DOCUMENTS-SPARK-PROVENANCE-20261109.json) records the dated manifest,
every feed SHA-256, generator hash, unchanged job/common-source hashes,
compiled jar hash, offline compiler jars, Spark/Python/Java versions, exact
local container image ID and each lakehouse publication's immutable path and
runtime hash. Every lakehouse native-input manifest equals the legacy manifest.
Compaction records the resolved hourly version it actually read. The generator
was not rerun between legacy and converted execution.

The unchanged Scala classes compile offline with the Scala 2.12.18 compiler
bundled with PySpark 3.5.3. No sbt/Maven resolution or rewritten Scala/Python
oracle was used. Reproduce from the repository root:

```sh
export NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
export SPARK_LOCAL_IP=127.0.0.1
lakehouse/.venv/bin/python -m lakehouse.parity.documents_spark_fixture --landing warehouse/landing --business-date "$BUSINESS_DATE"
mkdir -p lakehouse/.data/$NS/spark-build/classes
java -cp 'lakehouse/.venv/lib/python3.12/site-packages/pyspark/jars/*' \
  scala.tools.nsc.Main -usejavacp -d lakehouse/.data/$NS/spark-build/classes \
  etl/spark/scala/src/main/scala/sfx/BatchSupport.scala \
  etl/spark/scala/src/main/scala/sfx/DocsShareActivity.scala \
  etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala
jar cf lakehouse/.data/$NS/spark-build/documents.jar -C lakehouse/.data/$NS/spark-build/classes .
lakehouse/.venv/bin/python -m lakehouse.parity.documents_spark_legacy --landing warehouse/landing --business-date "$BUSINESS_DATE" --jar lakehouse/.data/$NS/spark-build/documents.jar
lakehouse/.venv/bin/python -m lakehouse.runtime.documents_spark --landing warehouse/landing --business-date "$BUSINESS_DATE" --jobs docs_storage_by_owner docs_share_activity docs_folder_legacy_report docs_search_log_parse docs_tag_normalize docs_event_export_hourly lake_compaction_documents
DOCUMENTS_SPARK_JOB=all DBT_PARTIAL_PARSE=0 lakehouse/.venv/bin/python -m lakehouse.runtime.dbt --select 'spark_docs_storage_by_owner spark_docs_share_activity spark_docs_folder_legacy_report spark_docs_search_log_parse spark_docs_tag_normalize spark_docs_event_export_hourly spark_lake_compaction_documents'
lakehouse/.venv/bin/python -m lakehouse.parity run --spec documents.spark_docs_storage_by_owner documents.spark_docs_share_activity documents.spark_docs_folder_legacy_report documents.spark_docs_search_log_parse documents.spark_docs_tag_normalize documents.spark_docs_event_export_hourly documents.spark_lake_compaction_documents --business-date "$BUSINESS_DATE"
make sfx-lakehouse-test NS=$NS LEGACY_NS=$LEGACY_NS BUSINESS_DATE=$BUSINESS_DATE
make sfx-lakehouse-airflow-test NS=$NS LEGACY_NS=$LEGACY_NS BUSINESS_DATE=$BUSINESS_DATE SFX_LH_LANDING=warehouse/landing SFX_LH_AF_DAG_TEST=0
```

Scala compilation completed with one deprecation warning. The legacy helper
uses the existing local `postgres:16` image only as an isolated Linux filesystem,
not as a database or Spark implementation. Read-only host Java, Java security
configuration, Python/Spark and UID/GID mappings provide its runtime; Docker
networking is disabled. Initial attempts exposed missing Java configuration,
HOME/Ivy and UID mapping; the helper supplies these explicitly. It runs the
original job files/classes directly in local Spark, not the cluster-specific
legacy submit scripts.

Actual legacy job output:

```text
legacy.spark.docs_storage_by_owner: SUCCEEDED
legacy.spark.docs_share_activity: SUCCEEDED
legacy.spark.docs_folder_legacy_report: SUCCEEDED
legacy.spark.docs_search_log_parse: SUCCEEDED
legacy.spark.docs_tag_normalize: SUCCEEDED
legacy.spark.docs_event_export_hourly: SUCCEEDED
legacy.spark.lake_compaction_documents: SUCCEEDED
```

## Lakehouse models, publication and scheduling

Native Spark transformations are independent of the BTEQ snapshots and retain
the Python explicit schemas/UDFs and Scala CSV inference. Runtime sources are
date-scoped Delta tables, declared in `sources.yml` with business-date identifiers.
Each distinct silver dbt model uses `source()` and filters its business date.
Date-scoped schema replacement preserves Scala's inferred empty-input schema
without corrupting another date. Unit tests cover header-only inference,
same-date replay, cross-date retention and empty export/compaction behavior.

The models are enabled by `DOCUMENTS_SPARK_JOB=<job>` (or `all` for explicit
validation). Each job DAG sets this value and selects its own model and tests.
The default BTEQ `tag:documents` task therefore cannot activate paused/manual
Spark sources or depend on an hourly artifact that has never been produced.
The native users APP_USER feed has an explicit users-domain readiness edge.

| Job | UTC schedule | Initial state |
|---|---|---|
| docs_storage_by_owner | 04 01 daily | enabled |
| docs_share_activity | 05 01 daily | enabled |
| docs_folder_legacy_report | none | paused, manual only |
| docs_search_log_parse | 12 02 daily | enabled |
| docs_tag_normalize | 14 02 daily | enabled |
| docs_event_export_hourly | 18 * * * * | paused |
| lake_compaction_documents | 19 02 daily | paused with its producer |

Keeping compaction paused is an explicit operational choice: the hourly
producer is intentionally paused. Enable the producer before enabling its
daily consumer. Compaction uses a date-scoped committed-artifact FileSensor,
in Airflow reschedule mode, rather than holding a Spark task/namespace lock
while waiting. The local sequential runner requires the producer to have run
first. No scheduler was started and no legacy cron was disabled by this patch.

Hourly output is a full snapshot partitioned by Spark
`pmod(DOCUMENT_ID, 10000)`, including nonnegative buckets for negative IDs.
A write goes to a unique retained version, must have `_SUCCESS` and unchanged
input hashes, then atomically replaces one POSIX symlink. Readers pin resolved
paths; compaction reads the selected immutable version and uses `coalesce(4)`.
Retried exports have identical rows/buckets, not identical UUIDs or filenames.
Failed writes, missing success markers, validation failures and failed pointer
swaps leave the prior public snapshot intact. Tests include empty publication
and a glob reader through a published pointer. Atomicity is per Parquet
publication, not a distributed transaction across Delta, dbt or multiple jobs.

Both real exports have **66 bucket directories**. Both real compacted outputs
have **3 Parquet files**, no bucket subdirectories, and identical 68-row output.
Coalesce has an upper bound of four files; it does not force four or require
matching generated filenames. A completely empty partitioned export has no
data files: export succeeds, while the unmodified Scala-style compactor fails
schema inference. This behavior is preserved, not normalized away.

## Results and assumptions

```text
documents.spark_docs_event_export_hourly: PASS {'legacy': 68, 'lakehouse': 68}
documents.spark_docs_folder_legacy_report: PASS {'legacy': 10, 'lakehouse': 10}
documents.spark_docs_search_log_parse: PASS {'legacy': 68, 'lakehouse': 68}
documents.spark_docs_share_activity: PASS {'legacy': 51, 'lakehouse': 51}
documents.spark_docs_storage_by_owner: PASS {'legacy': 17, 'lakehouse': 17}
documents.spark_docs_tag_normalize: PASS {'legacy': 68, 'lakehouse': 68}
documents.spark_lake_compaction_documents: PASS {'legacy': 68, 'lakehouse': 68}
Done. PASS=22 WARN=0 ERROR=0 SKIP=0 TOTAL=22
```

Seven dbt models and 15 data tests cover keys, counts, tag/action invariants and
bucket semantics. All 21 coverage entries also reference the named cron test:
`test:lakehouse/tests/test_documents_spark.py::test_documents_spark_cron_replacements`.

Assumptions A-210 through A-216 cover the dated feeds, disabled report, hourly
cadence/buckets, local atomic publication, paused daily compaction, independent
models/cron wiring and empty partitioned exports. A-044 is the historical
foundation stub decision; A-212 replaces the stub while retaining pausedness.
Existing A-037/A-044 coverage links are retained.

Requested test result:

```text
Pipeline: 8 DAGs, 112 tasks, valid
157 passed, 1 warning in 65.39s (0:01:05)
```

Airflow DAG import, dependencies, sensor paths and rendered templates:

```text
1 passed in 1.15s
```

An initial full test exposed lost historical assumption links; those were
restored, not removed from the test. The one remaining warning is the existing
dbt `datetime.utcnow()` deprecation. This is fixture/local filesystem parity,
not production scheduler, distributed-worker/object-store atomicity, a
full Airflow DAG execution, or a populated-estate migration. Retained version
garbage collection and all shared integration responsibilities remain outside
this step. No UI changed.
