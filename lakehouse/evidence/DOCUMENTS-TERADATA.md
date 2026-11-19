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

- Latest DOC_VERSION and dependent views build: `Done. PASS=12 WARN=0 ERROR=0 SKIP=0 TOTAL=12`.
- The earlier exact-only full parity run failed on the three tied-version specs.
  All three now PASS their explicitly approved candidate-set comparisons.
- After fixing duplicate-aware staging comparison,
  `documents.stg_storage_usage_daily: PASS {'legacy': 2100, 'lakehouse': 2100}`.
- Current reports: 24 documents specs PASS; three use tie-aware candidate sets.
- `make sfx-lakehouse-test`: `111 passed, 1 warning in 41.95s`.
- Coverage and assumptions validation: zero errors, with pending work retained.
- Graph: `Pipeline: 2 DAGs, 76 tasks, valid`.

## Approved tie policy and candidate-set parity (A-200)

The fixture deliberately supplies 50 document groups with tied VERSION_TS.
The legacy SQL orders only by VERSION_TS DESC. The approved deterministic
policy selects the latest timestamp, then highest VERSION_ID. A-200 is
accepted, risk med. A read-only comparison of all 450 emulator winners
against this ordering found 49 different winners, starting at document
9000000001. Of the 50 tied groups, the emulator agrees in one and differs
in 49. Exact-only parity failed; it was not silently normalized to PASS.

The approved deterministic tie-breaker is implemented and tested on multiple
tied groups, including a newer timestamp with a lower VERSION_ID. No parity
normalization or legacy edits were made. The three specs now explicitly expand
legal tied winners from legacy staging, matching every candidate column:

| Spec | Exact matched | Tie resolved | Mismatches |
|---|---:|---:|---:|
| documents.doc_version | 400 | 50 | 0 |
| documents.v_document_versions | 400 | 50 | 0 |
| documents.v_workspace_storage | 200 | 50 | 0 |

Untied documents retain exact comparisons to the published legacy outputs.
Workspace totals are recomputed from legacy candidate contributions matching
the lakehouse's selected version IDs, then checked against possible per-owner
minimum and maximum totals. Untied owners also match the legacy published
count and total exactly. All 250 owner bounds are checked. Candidate input
counts are 500 legacy rows and 450 lakehouse contribution rows, not 250 owners.
See `lakehouse/parity/README.md` for the opt-in generic comparison contract.

The three output inventory IDs plus BTEQ 02_current_versions and its stage
identity are now converted using fresh PASS evidence. Later documents work
and shared integration objects remain pending.

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
