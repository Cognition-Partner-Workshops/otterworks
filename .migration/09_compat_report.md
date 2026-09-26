# 09 MongoDB Atlas compatibility report (mmp_rt_src -> mmp_rt_billing_n)

Evidence: `.migration/census/source_census.{md,json}`, `.migration/census/app_code_census.md`
(read-only census, 2026-09-26, principal `mmp_rt_source` = `read@mmp_rt_src`). Field names and
types only; no document values anywhere in `.migration/`.

## 1. Version and feature gaps
- Source server 8.0.32 enterprise, 3-member replica set `atlas-lfpftr-shard-0`, primary healthy.
  Target is the same cluster (`otterworks-demo`, M0): version gap = none, FCV gap = none by
  construction. FCV could not be read (`getParameter` Unauthorized for `read`); recorded, not blocking.
- No views, capped, time-series, validators, TTL, unique or partial indexes, no `system.js`.
  Nothing uses a deprecated or removed feature. `$where`/`mapReduce`/`eval`: zero hits in code.
- 6 collections, ~6 MB, max document 274 B: far inside M0 limits (512 MB, 100 ops/s throttle);
  batch inserts of 1,000 docs keep the load under a minute per collection.

## 2. Bucket per object (exactly one)
| Object | Bucket | Justification |
|---|---|---|
| users (500) | migration unit | root entity; referenced by folders/documents/comments/shares/audit_events |
| folders (300) | migration unit | tree via `parentId` (119 roots) |
| documents (5000) | migration unit | `price` Decimal128, `tags` array |
| comments (12000) | migration unit | 15 orphans (see M1) |
| shares (3000) | migration unit | fields are `documentId, granteeId, permission, expiresAt` (intake named `userId/folderId`; census wins) |
| audit_events (20000) | migration unit | `ts` mixed date/string (see M4) |
| shared/reference | none | no lookup or code table exists |
| proposed-unused | none | all six carry data; no evidence of disuse |
| excluded | none | |

## 3. Index review (equivalence required by tol-v1)
| Collection | Non-`_id` indexes on source | Target plan |
|---|---|---|
| users | `email_1` (not unique) | recreate as-is; do NOT make unique (M3) |
| folders | none | none |
| documents | `ownerId_1_updatedAt_-1` | recreate as-is |
| comments | `documentId_1` | recreate as-is |
| shares | none | none |
| audit_events | `ts_1` | recreate as-is |
Children create indexes with identical key/options and paste `getIndexes()` of both sides in the PR.

## 4. Shard-key review
Source is unsharded (`listShards` CommandNotFound = replica set, single shard name). Target M0 is
unsharded. No shard keys. Not applicable.

## 5. Driver versions and app touchpoints
No MongoDB driver (`mongodb`, `mongoose`) in any `package.json` in the repo; `collab-service` is
Redis-backed; `frontend/` only labels an engine badge. There is no application code to rewrite for
this engagement: units are data movement + index parity + recon. The repoint at cutover is a
connection-string/database-name change performed by the customer on the real consumers (DEP-002).

## 6. Data-quality decisions (proposed; approved at STOP B)
| ID | Finding (count) | Decision (recommended) | Alternative |
|---|---|---|---|
| M1 | 15 comments whose `documentId` matches no document | migrate all 12,000 as-is (BSON identity, exact count parity); batch w1-b03 additionally writes the 15 `_id`s into `mmp_rt_billing_n._dq_comments_orphans` (`{_id, documentId, reason:"orphan_documentId"}`) as a customer work-list. Deleting source rows is out of scope (source read-only); deleting target rows changes scope and would need a human row. | drop the 15 at load (breaks exact count parity; needs a tolerance change) |
| M2 | 5 documents with `folderId: null` (0 missing, 0 orphans) | keep `null` as-is; graded with `null_missing_equiv` (STOP A P2). Nulls mean "not in a folder" (same as the 119 root folders with `parentId: null`). | none |
| M3 | 3 case-variant duplicate e-mail groups (6 users); `email_1` is not unique | migrate all 6 as-is; keep `email_1` non-unique. Recorded as customer follow-up: choose canonical account per group, then add a case-insensitive unique index post-cutover. | collapse duplicates at load (loses rows; identity broken) |
| M4 | 20 of 20,000 `audit_events.ts` stored as ISO-8601 strings (`YYYY-MM-DDTHH:MM:SS+HH:MM`), all parse | convert to BSON date at load so the target has one type and `ts_1` sorts correctly. Graded by spec alias `audit_ts_string_to_date` (`date_string_to_date`, format `%Y-%m-%dT%H:%M:%S%z`, then `datetime_utc_truncate_ms`). | keep strings (type defect persists) |
| M5 | `documents.price` is Decimal128 | identity (Decimal128 -> Decimal128), `bson_type: decimal`, exact sum parity at Tier 2 | none |

## 7. Operations, backup, monitoring
Same Atlas project/cluster: backup policy, alerts and monitoring already cover `mmp_rt_billing_n`.
Post-cutover the customer retires `mmp_rt_src` (drop) on their own schedule; no Devin action.

## 8. mongosync eligibility
Version-eligible (8.0 >= 6.0) but not usable here: `mongosync` binary absent, source principal lacks
`clusterMonitor`/oplog read, and source+target share one cluster (mongosync forbids same-cluster).
Movement = pymongo scoped loader per collection, drop+reload idempotent; final catch-up = reload +
recon at cutover prep (seconds at 6 MB).

## 9. Fixture
Synthetic, generated by `migration/mmp_rt/fixture/generate_fixture.py` from the type census
(no production values), loaded once by the orchestrator into `mmp_rt_billing_n.fx_src_<collection>`
(10%: users 50, folders 30, documents 500, comments 1200, shares 300, audit_events 2000; plants
2 orphan comments, 5 null folderIds, 2 dup-email groups, 10 string `ts`). Fixture DSN secret =
`MONGODB_MMP_RT_TARGET_N_URI`, `--source-db mmp_rt_billing_n`, mapping copy
`migration/mmp_rt/fixture_mapping_spec.json`. Manifests: `.migration/fixtures/w1-b0N.json`.
