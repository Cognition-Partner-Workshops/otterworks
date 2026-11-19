# Audit batch outputs

The daily graph builds the warehouse SQL outputs, then the Spark outputs, then
optimizes the Delta Spark summary. Spark's headered landing schemas differ from
the warehouse PSV schemas. Set `AUDIT_SPARK_LANDING` to the same **frozen snapshot**
directory used by the legacy Spark jobs; its default is
`etl/spark/.data/$LEGACY_NS/landing`. This snapshot contains all files in each
table directory, matching legacy Spark, and BUSINESS_DATE identifies the batch,
not an event-date filter.

For the local fixture, generate it with
`python3 etl/spark/fixture/generate_fixture.py --rows 2000 --seed 1110`
with `NS=sfx-d1110-before`. Start the legacy estate using its documented
`make sfx-spark-up` target, then run each audit job with
`NS=sfx-d1110-before JOB=<job> bash etl/spark/run.sh`.
All six Spark parity specs compare those Parquet outputs with the Delta
tables built from this identical landing. JDBC sinks contain the same logical
rows and are retired, not duplicated in the lakehouse (A-406).

The independent `lakehouse_audit_weekly` Airflow DAG uses `@weekly` (Sunday
00:00 UTC), with the guide's logical-date-minus-one-day BUSINESS_DATE.
Configure `AUDIT_ARCHIVE_BUCKET`, `AUDIT_ARCHIVE_OWNER`, and AWS credentials
through the deployment environment before enabling execution in an estate.
The entry point is `python -m lakehouse.audit.archive --business-date YYYYMMDD`.
No real AWS services are needed for the archive tests.

Archive publication writes Glacier JSONL, a Standard-class key-only manifest,
deletes the source keys, then publishes the compliance report. A retry resumes
the manifest and never downloads Glacier. A completed business-date report is
immutable; late arrivals wait until the next weekly run. Conflicting incomplete
snapshots fail closed. This assumes immutable DynamoDB event keys and payloads
during archival (A-407). Test parity compares decompressed event multisets and
reports excluding gzip-dependent size and execution timestamp, not gzip bytes.

The disabled Informatica archive responsibility is preserved by the default-off
dbt gate and absence of an independently scheduled Informatica task. An enabled
append/sequence-history migration is **not** verified; A-403 remains open.
