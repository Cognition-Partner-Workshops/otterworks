# Documents Teradata conversion checkpoint

Namespace: `sfx-d1110-after`; legacy: `sfx-d1110-before`;
business date: `20261109`; shared input: `warehouse/landing`.
Legacy code and landing files were not changed by this conversion.

Implemented 20 silver staging/publication models and four gold outputs,
24 output parity specs, and their daily graph nodes. Existing bronze source
declarations and readiness tasks already cover the ten documents feeds.
Ownership lists 97 documents-only objects, including later pending work.
Shared objects, monthly storage billing, global schedules and runners remain
outside documents ownership.

## Verification

- dbt documents build: `Done. PASS=51 WARN=0 ERROR=0 SKIP=0 TOTAL=51`.
- `make sfx-lakehouse-parity`: failed; see individual JSON reports and PARITY.md.
- After fixing duplicate-aware staging comparison,
  `documents.stg_storage_usage_daily: PASS {'legacy': 2100, 'lakehouse': 2100}`.
- Current reports: 21 documents specs PASS, three FAIL.
- `make sfx-lakehouse-test`: `100 passed, 1 warning in 40.47s`.
- Coverage and assumptions validation: zero errors, with pending work retained.
- Graph: `Pipeline: 2 DAGs, 76 tasks, valid`.

## Unresolved exact-parity blocker (A-200)

The fixture deliberately supplies 50 document groups with tied VERSION_TS.
The legacy SQL orders only by VERSION_TS DESC. Spark and PostgreSQL choose
different valid winners for one group: version IDs 9000000049/9000000050.
This changes one workspace's TOTAL_BYTES by one byte (4144 vs 4145).
The failed specs are documents.doc_version, documents.v_document_versions and
documents.v_workspace_storage. Their three inventory objects plus BTEQ
02_current_versions and its stage identity remain pending.

No deterministic tie-breaker or normalization hiding this difference was added.
An approved tie policy/equivalence contract is required before claiming those
objects converted. The current JSON evidence deliberately records the failures.

## Other preserved behavior

- SEARCH_INDEX_LOG initializes empty and receives no staging rows, matching the
  missing legacy publication step. Empty incremental append retains target rows.
- STORAGE_USAGE_DAILY applies SET full-row deduplication; staging retains all
  2100 rows, including 50 exact duplicate pairs. Canonically numbered full rows
  compare staging multisets without losing multiplicity or null values.
- M_STORAGE_TOTALS has a reusable parameterized SQL macro and a gold table for
  the business-date month. Monthly billing writes and file export are not owned.
- Native loader transport/distribution remains subject to foundation assumptions;
  these results exercise the executable PostgreSQL emulator.
