# Billing Spark outputs and scheduling

Step 5 covers six billing PySpark jobs, their six submit wrappers and six
individual `etl/crontab` entries. It does not convert the remaining consumers
or certify whole-domain completion. No legacy source is edited.

## Inputs and independent oracle

`billing/spark_inputs.py` declares a separate
`warehouse/landing/billing-spark/20261109/` bundle. These are **not** warehouse
bronze or BTEQ feeds. The schema is the alternate `common/schemas.py` contract:
BIGINT, nullable strings, DATE/TIMESTAMP and DECIMAL(18,2). Every table has two
headered date-named PSV files, and both engines read the complete wildcard set.
An exact schema/header/file-set/hash manifest is checked before execution and
again before publication. Missing inputs are errors, not empty deliveries.
The input-ready receipt is namespace/date scoped and follows validation.

The nine tables are PLAN_CATALOG, SUBSCRIPTION, INVOICE_HDR, INVOICE_LINE,
PAYMENT, GL_ACCOUNT, GL_JOURNAL_LINE, CREDIT_NOTE and USAGE_DAILY. Fixtures
include both dates, nulls, quoted delimiters, negative and zero amounts,
orphan foreign keys, unused dimensions, duplicate projected payment rows,
null GL currencies and debit/credit values, and case-sensitive churn status.
Empty and malformed-input cases are covered separately by tests.

`billing/spark_reference.py` executes all six **unchanged actual legacy Python
scripts** with Spark submit, not a rewritten query oracle. JDBC input tables
for payment aging are loaded from the same immutable PSV snapshots into the
isolated `billing_spark_<NS>` PostgreSQL database. That database also receives
the three actual JDBC outputs. It never overwrites BTEQ or Informatica tables.
Source and input hashes, driver hash and runtime version are recorded alongside
the native outputs. Two local cores/shuffle partitions replace cluster resource
tuning; production performance is not established. The submit wrappers are
source-reviewed rather than invoked: cluster paths and embedded credential
exports are not propagated. The reference subprocess removes AWS variables.

## Nine physical parity surfaces

All six raw Parquet outputs are compared independently. Invoice summary, GL
trial balance and usage also have distinct parity specs reading the native
PostgreSQL tables versus their separately persisted Delta replacements.
No consumer is silently redirected to those replacements.

Comparison views sort **every output column**, NULLS FIRST, and add a
comparison-only `parity_row`; PostgreSQL text ordering uses `COLLATE "C"` to
match Spark's UTF-8 binary ordering. This is a bag comparison: identical duplicates
remain separate rows; nullable keys and duplicate payment projections are not
discarded. Physical Parquet/Delta outputs have no artificial ordinal. Decimals
and churn doubles are compared exactly; no tolerance or case normalization is
used. Payment aging uses its frozen JDBC input snapshot rather than BTEQ payment
semantics. GL NET is SUM(debit-credit), not SUM(debit)-SUM(credit). Null group
keys do not match the subsequent legacy equality joins. Usage selects the
maximum date over all wildcard files, not implicitly BUSINESS_DATE.

## Retry, append and failure boundaries

Raw legacy usage **duplicates on replay**. The requested lakehouse behavior is
explicitly delivery-idempotent instead: same business date and input/code hash
is a no-op; a changed completed append delivery is rejected. A distinct delivery
appends once even when its selected usage date is unchanged. Duplicates within
a delivery remain intact. Snapshot jobs overwrite changed same-date inputs and
allow explicit older-date reruns. This intentional difference is A-128, not a
claim of native replay parity.

Each publication writes immutable raw Parquet and, when applicable, Delta
directories, validates the input signature, stores its delivery ledger, then
atomically replaces one POSIX `current` symlink. Failures before commit leave
the old pair visible; retries can recover from a leftover temporary link.
Comparison-view DDL is separately retryable after commit. Tests inject input
mutation and commit failure, then verify both physical outputs and duplicate
multiplicity. Versions/orphans are retained for inspection. No consumers are
retargeted (A-127). Full-history append rewrites, cleanup, non-POSIX deployment
and production-scale recovery remain open under A-129/A-130.

Six paused UTC DAGs preserve the exact 01:00, 01:01, 01:02, 01:03, 02:10 and
02:15 schedules, with validation -> readiness -> job -> parity success edges.
They use the foundation 20261110 start date, date-minus-one logical convention,
one active run/task and namespace serialization. Historical dates require
explicit backfill. Named verification: `test_billing_spark_cron_replacement`.
Actual scheduling activation and live secrets/consumer wiring are not tested.

## Reproduction

From the repository root, with the existing local PostgreSQL emulator and JDBC
driver cache (`etl/spark/fixture/fetch_jars.sh`) available:

```sh
export NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
export SPARK_LOCAL_IP=127.0.0.1
export TD_PG_PORT="$(python3 -c 'import os,zlib;print(54500+zlib.crc32(os.environ["LEGACY_NS"].encode())%1000)')"
python=lakehouse/.venv/bin/python
NS="$LEGACY_NS" bash etl/spark/fixture/fetch_jars.sh
"$python" -m lakehouse.billing.spark_inputs --landing warehouse/landing --business-date "$BUSINESS_DATE" --generate
"$python" -m lakehouse.billing.spark_reference --landing warehouse/landing --business-date "$BUSINESS_DATE"
"$python" -m lakehouse.billing.spark --landing warehouse/landing --business-date "$BUSINESS_DATE"
make sfx-lakehouse-parity NS="$NS" LEGACY_NS="$LEGACY_NS" BUSINESS_DATE="$BUSINESS_DATE"
SFX_LH_INFA_NATIVE_TEST=1 make sfx-lakehouse-test NS="$NS" BUSINESS_DATE="$BUSINESS_DATE"
"$python" -m lakehouse.orchestration check
```

Do not regenerate inputs between engines. The reference command resets only
its isolated fixture estate; `--append-existing --jobs billing_usage_append_daily`
deliberately demonstrates raw native duplicate append, after which restore the
matching one-delivery reference before parity. Run tasks through the serialized
orchestrator; direct CLIs must not overlap other Spark tasks in the same namespace.

Assumptions A-125 through A-130 cover input identity, expressions/bags, physical
outputs, intentional replay policy, cron/resources and publication/recovery.

## Recorded verification

Branch: `devin/1795091104-lakehouse-billing-spark`, cut from fresh
`origin/demo-data-platform-after` after PR #2957 merged.

All six actual native jobs completed. All nine new physical-output specs PASS:
churn Parquet 3 rows; trial-balance Parquet/JDBC 4 each; invoice-summary
Parquet/JDBC 3 each; payment-aging Parquet 5; revenue-by-plan Parquet 2;
usage Parquet/JDBC 2 each. Exact identical-delivery replay observed native
Parquet/JDBC grow to 4/4, while converted Parquet/Delta stayed 2/2. The isolated
reference was then restored to one delivery before final parity. Development
append artifacts from an earlier code revision were preserved under
`.data/<NS>/billing_spark_recovery/`, then the final-code baseline was published.

Final checks (all exit 0):

```text
Parity: 196 PASS, 0 FAIL
Assumptions: 133 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 0 errors
Pipeline: 25 DAGs, 306 tasks, valid
281 passed, 9 warnings in 244.17s (0:04:04)
Airflow: 2 passed in 2.05s
Ran 323 rules on 5 files: 0 findings.
```

Warnings are the existing dbt datetime deprecations. Airflow verification used
`SFX_LH_AF_DAG_TEST=0` (real DagBag/template imports, not live scheduler dispatch).
The five scanner false positives on safely composed psycopg identifiers and
argv-only subprocess execution use narrow annotations consistent with the
existing oracle helpers; no scan configuration was weakened.

Exactly 18 owned IDs changed: six jobs and six submits to converted, six cron
entries to replaced_by_platform. All other 420 coverage entries, all preexisting
assumptions and all 19 existing DAGs are unchanged. Six DAGs were added. The
187 old parity reports' metadata-only refreshes were excluded; the nine new
reports and provenance are retained. Thirteen billing-owned consumer/integration
IDs outside this step remain pending. No scoped ID remains pending, subject to
the explicit A-129/A-130 operational risks.

Persistent local logs: `/home/ubuntu/billing-spark-{reference-final,replay,parity,tests,airflow,semgrep}.log`.
