# Users Spark parity

Run the group using the command in `../README.md`. Local prerequisites additionally
include Java 17/21 (with `javac`/`jar`), PySpark 3.5.3 and NumPy in `warehouse/.venv`:
`uv pip install --python warehouse/.venv/bin/python pyspark==3.5.3 numpy==1.26.4`.

The hook snapshots the six PostgreSQL `STG_` inputs once and supplies identical
Parquet inputs to both sides. The baseline executes compatible Python source files
with only session/landing/save adapters, and compiles the two unchanged Scala job
bodies with `LegacySupport.scala` replacing only I/O. Spark writes baseline Parquet;
the target independently executes SQL and Python over the staged inputs. No legacy
output is used to populate any target. Runtime inputs and logs live under
`migration/dw-exit/.runs/<run-token>/users-spark/`.

The SQL file is Snowflake SQL using the run database and USERS schema. The hook's
Python parsers, logistic model and six-step label propagation are the local
Snowpark-Python conversion, not evidence of execution in Snowflake. All Snowflake
columns must remain red. Local proof does not change migration/licence state.

## Owner decisions/defaults

* The local warehouse fixture is not the legacy Spark fixture: activity has
  ACTIVITY_DT/DOCUMENT_COUNT rather than ACTIVITY_DATE/ACTION_COUNT; preferences
  have PREF_NAME/PREF_VALUE rather than PREF_JSON; login has CLIENT_TYPE rather
  than USER_AGENT. Default: leave the four affected jobs red with exact missing
  columns, rather than inventing semantics or substituting synthetic outputs.
  Owners need to supply real legacy-compatible inputs or approve a mapping.
* The manifest calls all six targets dbt models. Classification and existing
  `warehouse/snowpark` implementations assign graph, JSON, user-agent parsing and
  risk scoring to Snowpark Python. Default: keep those four in Python; do not edit
  the shared manifest. Owners should reconcile that metadata.
* Graph components retain exactly six propagation steps and exclude isolated users,
  rather than computing unrestricted connected components. Default: preserve legacy.
* JSON retains Python `str` values (`False`, `None`, etc.) and catches only
  ValueError/TypeError. Valid non-object JSON still raises AttributeError, as in the
  legacy UDF. Default: preserve the error, not silently flatten arbitrary JSON.
* Risk NULL inputs default to NULL (existing Snowpark implementation); Scala's
  primitive Int UDF semantics may differ on future NULL fixtures. This board proves
  only the measured inputs. Owner should decide a future NULL/32-bit overflow contract.

Group unit checks: `warehouse/.venv/bin/python -m pytest -q migration/dw-exit/users/spark-jobs/test_hook.py`.
