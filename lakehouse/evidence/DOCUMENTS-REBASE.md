# Documents integration rebase

Rebased `devin/1795075161-lakehouse-documents` onto fetched
`origin/demo-data-platform-after` (`9069712c4`), including the merged users work.

## Conflict resolution

- Kept users and documents pipeline nodes. Documents parity stays in the daily
  DAG; users Spark/activity DAGs remain separate and unchanged.
- Preserved both domains' coverage and assumptions, including exactly A-200
  through A-229 from documents. Coverage, assumptions and sources YAML merged
  automatically; generated Markdown conflicts were regenerated from the union.
- Combined extendable upstream graph/coverage tests with documents assertions.
- Kept upstream JSON/JSONL readers and documents namespace-qualified PostgreSQL
  readers. Initial validation exposed the upstream literal-only database rule
  rejecting `lakehouse_documents_infa_{NS}`. Validation now permits that existing
  placeholder while preserving lowercase literal checks and rejecting unknown
  placeholders. Static users database names do not require NS. Nine regression
  cases cover valid/empty/invalid names and both reader dispatch paths.

A source-level merge audit confirmed every non-owned coverage entry, every
upstream assumption and all users-specific pipeline nodes/DAGs are unchanged
from the fetched branch. No legacy source changes were made by this rebase.

## Checks after the final runtime edits

`make sfx-lakehouse-coverage NS=sfx-d1110-after` (exit 0):

```text
Assumptions: 93 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 0 errors
Pipeline: 18 DAGs, 150 tasks, valid
```

The documents ownership assertion (exit 0):

```text
documents: 97 owned objects, zero pending
```

All 45 documents specs were rerun through `lakehouse.parity run`, with
NS=sfx-d1110-after, LEGACY_NS=sfx-d1110-before, business date 20261109 and the
running legacy PostgreSQL port 55395. Exit 0; all 45 PASS. Tail:

```text
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
218 passed, 1 warning in 107.35s (0:01:47)
```

The warning remains the existing dbt datetime.utcnow deprecation. No additional
Airflow execution or other-domain runtime parity was requested/run in this step.
Logs: `/home/ubuntu/documents-rebase-{coverage,parity,test}.log`.

## Subsequent audit integration rebase

Rebased onto `79091e67f` from `origin/demo-data-platform-after`. Preserved
audit DAGs/nodes, upstream non-owned coverage and assumptions (source-level
comparison passed). Kept upstream boto3 pin and weekly schedule support alongside
documents clients and cron support. Combined audit Spark CI setup with the
documents Informatica oracle preparation. Regenerated shared evidence markdown.

Post-rebase checks (all exit 0):

```text
Assumptions: 102 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 0 errors
Pipeline: 19 DAGs, 185 tasks, valid
documents: 97 owned objects, zero pending
246 passed, 1 warning in 141.72s (0:02:21)
```

All 45 documents parity specs PASS, retaining zero mismatches for the three
tie-aware comparisons. Logs:
`/home/ubuntu/documents-ci-rebase-{test,parity}.log`.
