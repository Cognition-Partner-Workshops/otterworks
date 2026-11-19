# Documents external maintenance

The last four owned IDs are converted: search reindex and storage cleanup,
each with its own cron replacement. Legacy scripts and shared configuration,
helpers and integration objects remain unchanged. All 97 documents-owned IDs
are represented in `coverage/domains/documents.yaml`.

## Runtime and safety

`runtime/documents_external.py` accepts injected HTTP/AWS clients, timer and
clock. Native entrypoints use explicit requests/boto3 dependencies and the
unchanged `ETL_CONFIG_PATH`, API-key and bucket-owner environment interfaces.
Search remains Sunday **04:00 UTC** (`0 4 * * 0`); cleanup remains daily
**02:30 UTC** (`30 2 * * *`). Both DAGs start paused with zero automatic retries.
Named verification: `test_documents_external_cron_replacements`.

There is **no legacy dry-run flag**: its TODO explicitly says it was never
implemented. No new flag or implicit environment gate was invented. Cleanup
still copies before deletion, guards copy/delete/report with the expected
bucket owner, continues after individual move errors and counts failures.
Its report retains orphan-byte savings estimates even if some moves fail.
Listing retains the legacy absence of an ExpectedBucketOwner argument.

Search preserves delete-error tolerance, per-page batches of 100, task polling
deadlines, settings/defaults/nulls and both final count checks. Failed/expired
tasks do not themselves abort legacy execution; count mismatch still does.
No additional transport timeouts, retries or transactional guarantees are claimed.

Business date labels local receipts/evidence, not historical external state.
Cleanup keys and generated_at use UTC execution time. Backfill/catchup and
partial side effects must be reviewed before either DAG is unpaused. Local
receipts publish with atomic replacement; external operations are not atomic.

## Same-fixture unchanged-script oracle

Both engines receive fresh strict in-memory clients from the same JSON fixture
at `warehouse/landing/documents-external/20261109.json`, identical config,
fixture-only credentials and a frozen UTC clock. The harness imports and calls
the **unchanged legacy main functions**, then the native task functions.
Unknown HTTP endpoints fail locally; no real external systems are contacted.
This is service-contract parity, not a test of real IAM, MeiliSearch async
visibility, cloud consistency or SDK wire-level behavior.

Thirteen search scenarios cover 101-record pagination, empty input, queued,
failed, missing-UID and timed-out tasks, count mismatch, missing secret, and
delete/create/settings/service/index HTTP errors. Nine cleanup scenarios cover
paginated listing/scans, empty/all-referenced objects, zero-byte objects,
copy/delete failures, list/scan/report errors and missing/invalid owners.
Comparisons include full document/file indexes and settings, ordered HTTP calls,
serialized report.json bytes, ordered quarantine/delete/report actions, final
source/quarantine object states and exit/error outcomes. Authorization headers
in fake action records are redacted. No comparison normalization is used.

[Provenance](DOCUMENTS-EXTERNAL-PROVENANCE-20261109.json) records fixture hash,
unchanged legacy/helper hashes, converted runtime/harness/fake hashes, Python
runtime and the shared frozen clock. Generate the fixture only before either
engine runs; the harness rejects fixture changes during execution.

```sh
export NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before
lakehouse/.venv/bin/python -m lakehouse.parity.documents_external \
  --fixture warehouse/landing/documents-external/20261109.json \
  --business-date 20261109 --generate
make sfx-lakehouse-parity NS=$NS LEGACY_NS=$LEGACY_NS BUSINESS_DATE=20261109
```

The manual-only paused `lakehouse_documents_external_fixture` DAG runs the
existing fixture without regenerating it and then all five external specs.
It never runs the real-service native entrypoints.

## Assumptions

- **A-224:** exact paused cron replacements; activation/catchup review required.
- **A-225:** no dry-run; preserve copy/delete owner guards and partial failures.
- **A-226:** preserve search polling/count-validation and batching quirks.
- **A-227:** live-state/wall-clock semantics and nontransactional external writes.
- **A-228:** same-fixture unchanged-script oracle proves fake service contracts.
- **A-229:** explicit pinned client dependencies; shared helpers remain unowned.

Earlier open medium-risk A-208 (duplicate user lookups) and A-222 (Spark key/order
ties) remain open; this final batch does not establish production behavior for
those unreviewed input cases. All shared/integration objects remain pending.

## Final conversion checks

Commands ran from the repository root with DOMAIN=documents. Global strict
failure is expected under the domain-only contract: all 307 errors are pending
objects **outside** the 97 owned IDs; no integration object was reclassified.
The ownership assertion printed:

```text
documents: 97 owned objects, zero pending
```

`make sfx-lakehouse-coverage NS=sfx-d1110-after` (exit 0):

```text
Assumptions: 77 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 0 errors
Pipeline: 16 DAGs, 140 tasks, valid
```

`make sfx-lakehouse-parity NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109` (exit 0; all 46 specs):

```text
billing.customer_account: PASS {'legacy': 300, 'lakehouse': 300}
documents.collab_session: PASS {'legacy': 2000, 'lakehouse': 2000}
documents.doc_comment: PASS {'legacy': 2000, 'lakehouse': 2000}
documents.doc_share: PASS {'legacy': 1000, 'lakehouse': 1000}
documents.doc_tag: PASS {'legacy': 1000, 'lakehouse': 1000}
documents.doc_version: PASS {'legacy': 500, 'lakehouse': 450}
  exact_matched_rows=400 tie_resolved_rows=50 mismatches=0
documents.document: PASS {'legacy': 450, 'lakehouse': 450}
documents.external_cleanup_actions: PASS {'legacy': 9, 'lakehouse': 9}
documents.external_cleanup_report: PASS {'legacy': 9, 'lakehouse': 9}
documents.external_search_actions: PASS {'legacy': 13, 'lakehouse': 13}
documents.external_search_documents: PASS {'legacy': 13, 'lakehouse': 13}
documents.external_search_files: PASS {'legacy': 13, 'lakehouse': 13}
documents.file_object: PASS {'legacy': 2000, 'lakehouse': 2000}
documents.folder: PASS {'legacy': 200, 'lakehouse': 200}
documents.infa_doc_share: PASS {'legacy': 1000, 'lakehouse': 1000}
documents.infa_document: PASS {'legacy': 450, 'lakehouse': 450}
documents.infa_metrics: PASS {'legacy': 3, 'lakehouse': 3}
documents.infa_stg_document: PASS {'legacy': 450, 'lakehouse': 450}
documents.m_storage_totals: PASS {'legacy': 250, 'lakehouse': 250}
documents.search_index_log: PASS {'legacy': 0, 'lakehouse': 0}
documents.spark_collab_session_sessionize: PASS {'legacy': 4, 'lakehouse': 4}
documents.spark_doc_share_graph_reach: PASS {'legacy': 5, 'lakehouse': 5}
documents.spark_doc_version_diff_stats: PASS {'legacy': 11, 'lakehouse': 11}
documents.spark_docs_event_export_hourly: PASS {'legacy': 68, 'lakehouse': 68}
documents.spark_docs_folder_legacy_report: PASS {'legacy': 10, 'lakehouse': 10}
documents.spark_docs_folder_tree_walk: PASS {'legacy': 32, 'lakehouse': 32}
documents.spark_docs_search_log_parse: PASS {'legacy': 68, 'lakehouse': 68}
documents.spark_docs_share_activity: PASS {'legacy': 51, 'lakehouse': 51}
documents.spark_docs_storage_by_owner: PASS {'legacy': 17, 'lakehouse': 17}
documents.spark_docs_tag_normalize: PASS {'legacy': 68, 'lakehouse': 68}
documents.spark_file_object_binary_extract: PASS {'legacy': 11, 'lakehouse': 11}
documents.spark_lake_compaction_documents: PASS {'legacy': 68, 'lakehouse': 68}
documents.stg_collab_session: PASS {'legacy': 2000, 'lakehouse': 2000}
documents.stg_doc_comment: PASS {'legacy': 2000, 'lakehouse': 2000}
documents.stg_doc_share: PASS {'legacy': 1000, 'lakehouse': 1000}
documents.stg_doc_tag: PASS {'legacy': 1000, 'lakehouse': 1000}
documents.stg_doc_version: PASS {'legacy': 2100, 'lakehouse': 2100}
documents.stg_document: PASS {'legacy': 450, 'lakehouse': 450}
documents.stg_file_object: PASS {'legacy': 2000, 'lakehouse': 2000}
documents.stg_folder: PASS {'legacy': 200, 'lakehouse': 200}
documents.stg_search_index_log: PASS {'legacy': 2000, 'lakehouse': 2000}
documents.stg_storage_usage_daily: PASS {'legacy': 2100, 'lakehouse': 2100}
documents.storage_usage_daily: PASS {'legacy': 2050, 'lakehouse': 2050}
documents.v_document_versions: PASS {'legacy': 500, 'lakehouse': 450}
  exact_matched_rows=400 tie_resolved_rows=50 mismatches=0
documents.v_search_history: PASS {'legacy': 0, 'lakehouse': 0}
documents.v_workspace_storage: PASS {'legacy': 500, 'lakehouse': 450}
  exact_matched_rows=200 tie_resolved_rows=50 mismatches=0
```

`make sfx-lakehouse-test NS=sfx-d1110-after` (exit 0):

```text
204 passed, 1 warning in 95.07s (0:01:35)
```

The warning is the existing dbt datetime.utcnow deprecation. The dedicated
external tests also completed before the required full suite:

```text
30 passed in 0.71s
```

`lakehouse/.venv/bin/python -m lakehouse.coverage check --strict` (exit 1):

```text
Assumptions: 77 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 307 errors
ERROR: batch_runner:etl/run.sh: pending (--strict)
ERROR: bteq_script:warehouse/teradata/scripts/documents/10_storage_monthly.bteq: pending (--strict)
ERROR: etl_config:etl/config.ini: pending (--strict)
```

The full log contains only `pending (--strict)` errors for non-owned objects.
Production external-system execution, real cloud permissions and asynchronous
service behavior remain intentionally unverified.

`make sfx-lakehouse-airflow-test NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109 SFX_LH_LANDING=warehouse/landing` (exit 0):

Full DAG execution remained enabled (default SFX_LH_AF_DAG_TEST=1); this target
migrated local metadata and ran the actual `lakehouse_daily` DAG, not just an
import/template test. It does not execute the paused real-external-system DAGs.
The new native task entrypoints were exercised with injected clients in unit tests.

```text
1 passed in 1.01s
Done. PASS=3 WARN=0 ERROR=0 SKIP=0 TOTAL=3
Done. PASS=63 WARN=0 ERROR=0 SKIP=0 TOTAL=63
[2026-11-19T09:30:28.940+0000] {dagrun.py:905} INFO - DagRun Finished: dag_id=lakehouse_daily, execution_date=2026-11-10 00:00:00+00:00, run_id=manual__2026-11-10T00:00:00+00:00, run_start_date=2026-11-10 00:00:00+00:00, run_end_date=2026-11-19 09:30:28.940185+00:00, run_duration=811828.940185, state=success, external_trigger=False, run_type=manual, data_interval_start=2026-11-09 00:00:00+00:00, data_interval_end=2026-11-10 00:00:00+00:00, dag_hash=None
```

All command logs are retained under `/home/ubuntu/documents-final-*.log` on the
verification host. Standard Spark NativeCodeLoader fallback warnings occurred;
venv prefixes/dependency versions and Java were checked, and pip check printed
`No broken requirements found.` No environment workaround was introduced.
