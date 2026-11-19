# Documents Spark second batch

Five jobs, five submit wrappers, five cron identities and the documents-only
`binary_documents.py` library: **16 converted IDs**. Legacy source files,
submit scripts, cron and shared Spark libraries/configuration remain unchanged.
The first-batch fixture and its provenance remain separate and intact.

## Shared-input oracle and provenance

Both engines read `warehouse/landing/documents-second/spark/20261109`.
The unchanged legacy jobs run with a read-only `/opt/landing` bind mount,
network disabled and host Python 3.12/Spark 3.5.3/Java runtime mounts, exactly
as in the first batch. The existing local container image supplies isolation,
not rewritten Spark or an alternative oracle. These five jobs are Python;
the common launcher's recorded existing Scala jar is not executed by this batch.

The fixture contains 32 folders, 11 shares, 8 collaboration events,
11 versions, 13 file-object metadata rows and 12 blobs totalling 7298 bytes.
ZIP timestamps are fixed for reproducible blob hashes. The generator is not
rerun between engines. The manifest hashes every CSV and blob, including the
zero-byte file. Runtime validation checks the selected input set and hashes
before work and again before publishing an immutable output version.

[Provenance](DOCUMENTS-SPARK-SECOND-PROVENANCE-20261109.json) records the full
identical input manifests from both engines, manifest/generator/source hashes,
legacy job/library hashes, runtime image ID and versions, lakehouse runtime and
binary-library hashes, and each immutable output path. The first-batch legacy
`provenance.json` remains intact; this job subset has its own provenance file.

Reproduce from repository root after the first-batch setup:

```sh
export NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
export SPARK_LOCAL_IP=127.0.0.1
jobs='docs_folder_tree_walk doc_share_graph_reach collab_session_sessionize doc_version_diff_stats file_object_binary_extract'
lakehouse/.venv/bin/python -m lakehouse.parity.documents_spark_second_fixture --landing warehouse/landing/documents-second --business-date "$BUSINESS_DATE"
lakehouse/.venv/bin/python -m lakehouse.parity.documents_spark_legacy --landing warehouse/landing/documents-second --business-date "$BUSINESS_DATE" --jar lakehouse/.data/$NS/spark-build/documents.jar --jobs $jobs
lakehouse/.venv/bin/python -m lakehouse.runtime.documents_spark --landing warehouse/landing/documents-second --business-date "$BUSINESS_DATE" --jobs $jobs
DOCUMENTS_SPARK_JOB=all DBT_PARTIAL_PARSE=0 lakehouse/.venv/bin/python -m lakehouse.runtime.dbt --select 'spark_docs_folder_tree_walk spark_doc_share_graph_reach spark_collab_session_sessionize spark_doc_version_diff_stats spark_file_object_binary_extract'
lakehouse/.venv/bin/python -m lakehouse.parity run --spec documents.spark_docs_folder_tree_walk documents.spark_doc_share_graph_reach documents.spark_collab_session_sessionize documents.spark_doc_version_diff_stats documents.spark_file_object_binary_extract --business-date "$BUSINESS_DATE"
make sfx-lakehouse-test NS=$NS LEGACY_NS=$LEGACY_NS BUSINESS_DATE=$BUSINESS_DATE
make sfx-lakehouse-airflow-test NS=$NS LEGACY_NS=$LEGACY_NS BUSINESS_DATE=$BUSINESS_DATE SFX_LH_LANDING=warehouse/landing SFX_LH_AF_DAG_TEST=0
```

Actual unchanged-job results:

```text
legacy.spark.docs_folder_tree_walk: SUCCEEDED
legacy.spark.doc_share_graph_reach: SUCCEEDED
legacy.spark.collab_session_sessionize: SUCCEEDED
legacy.spark.doc_version_diff_stats: SUCCEEDED
legacy.spark.file_object_binary_extract: SUCCEEDED
```

Actual new specs (full-row exact comparison, no float tolerance):

```text
documents.spark_collab_session_sessionize: PASS {'legacy': 4, 'lakehouse': 4}
documents.spark_doc_share_graph_reach: PASS {'legacy': 5, 'lakehouse': 5}
documents.spark_doc_version_diff_stats: PASS {'legacy': 11, 'lakehouse': 11}
documents.spark_docs_folder_tree_walk: PASS {'legacy': 32, 'lakehouse': 32}
documents.spark_file_object_binary_extract: PASS {'legacy': 11, 'lakehouse': 11}
```

dbt built five models and ran 23 data tests:

```text
Done. PASS=28 WARN=0 ERROR=0 SKIP=0 TOTAL=28
```

## Preserved edge behavior and assumptions

- **A-217:** exactly twenty parent transitions, not convergence. Folder 25 in a
  25-node chain stops at folder 5 with depth 20. Three-node and self cycles
  continue for twenty iterations. Preserve dangling roots, null parents and
  the legacy `parent or current` behavior for a zero parent.
- **A-218:** user 1 is always seeded with distance zero; directed traversal
  stops after four hops. Cycles, self shares and duplicate edges cannot expand
  visited users repeatedly; the fifth-hop node and disconnected cycle stay out.
- **A-219:** group sessions by user/document, not source SESSION_ID. Unsorted
  events and duplicates are retained. An adjacent gap of exactly 1800 seconds
  stays in the same session; 1801 splits. Mixed null timestamps fail rather than
  receiving invented ordering or replacement times.
- **A-220:** ascending VERSION_NUMBER lag and the default, order-sensitive
  Python SequenceMatcher (including autojunk). Null bodies become empty only
  inside similarity, not in output columns. Exact double parity passes; no
  rounding or tolerance was introduced.
- **A-221:** preserve the lightweight PDF/ZIP/DOCX parser, not a replacement
  renderer. Tests cover media, decoded text, 4096-character truncation, page
  counts before truncation, SHA256, malformed PDF/ZIP/XML and DTD rejection.
  Metadata/blob joining is inner and retains duplicate references. The legacy
  log reports `BINARY_INPUT_FILES=12 BINARY_INPUT_BYTES=7298` and
  `BINARY_OUTPUT_ROWS=11`: Spark lists the empty blob but omits its data row.
  Direct empty-byte library extraction still returns an error tuple; corrupt
  nonempty blobs produce visible error rows. No empty-file row was invented.
- **A-222 (open, med):** duplicate folder IDs and tied per-document version
  numbers retain legacy unspecified ordering. The fixture has unique keys;
  this does not prove a migration policy for ties.
- **A-223:** isolated feeds and exact original UTC schedules: folder walk
  **03:21**, reach **03:23**, sessions **03:24**, diffs **03:25**, binary
  **03:26**. Dedicated DAGs retain the foundation logical-date convention,
  retries and date-scoped dbt outputs. The binary job has CSV readiness plus
  complete blob/CSV manifest validation; incomplete manifests fail and retry.

Named cron verification:
`test:lakehouse/tests/test_documents_spark.py::test_documents_spark_second_cron_replacements`.
Normal, empty and error cases also cover empty graph seeding, empty transforms,
missing binary directories, changed/missing blob hashes and session sort errors.

Full Airflow execution, distributed/object-store publication semantics and
populated-estate ambiguous-key migration are not established. Output version
garbage collection remains outside this batch. Remaining documents maintenance
scripts and integration-owned shared objects remain pending.
