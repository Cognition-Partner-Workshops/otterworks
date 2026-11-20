# Users Spark parity

Run the group using the command in `../README.md`. Local prerequisites additionally
include Java 17/21 (with `javac`/`jar`), PySpark 3.5.3 and NumPy in `warehouse/.venv`:
`uv pip install --python warehouse/.venv/bin/python pyspark==3.5.3 numpy==1.26.4`.

All six jobs use `etl/spark/fixture/generate_fixture.py`, fixed seed **1110** and
`BOARD_ROWS` rows (default 200). Its own generator logic produces every row; no
rows are hand-picked or mapped from incompatible warehouse schemas. The baseline
executes all four unmodified Python job files with the original typed PSV landing
reader, adapting only session/save. The two unchanged Scala job bodies are compiled
with `LegacySupport.scala` adapting only session and I/O paths; its CSV inference
matches the legacy BatchSupport reader. Spark writes the baseline Parquet outputs.
DuckDB independently reads the **same PSV files**, with types and column order from
`etl/spark/jobs/py/common/schemas.py`, into group-specific
`USERS.SPARK_FIXTURE_*` inputs. SQL/Python conversions read only those inputs.
No legacy output populates any target. Runtime inputs and logs live under
`migration/dw-exit/.runs/<run-token>/users-spark/`.

After the board make command, run
`BOARD_ROWS=200 warehouse/.venv/bin/python migration/dw-exit/users/spark-jobs/annotate_board.py`
to record the fixture source, seed, row setting and input namespace in the board's
measurement contract and reasons. This replaces the shared board's generic
PostgreSQL-source label without modifying shared code. Annotation is idempotent.

The SQL file is Snowflake SQL using the run database and USERS schema. The hook's
Python parsers, logistic model and six-step label propagation are the local
Snowpark-Python conversion, not evidence of execution in Snowflake. All Snowflake
columns must remain red. Local proof does not change migration/licence state.

## Owner decisions/defaults

* Resolved input-selection question: use the legacy Spark fixture for all six jobs,
  rather than the unrelated warehouse fixture. No owner mapping is needed.
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
