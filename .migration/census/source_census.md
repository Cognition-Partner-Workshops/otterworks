# Source Census — `mmp_rt_src` (MongoDB Atlas)

Branch: `tp-run/mongodb-20260926T170458Z-rt-fanout`. Read-only access via `MONGODB_MMP_RT_SOURCE_URI`. No document values recorded — metadata, field names, types, and counts only.

## A. Discovery

| Command | Result |
|---|---|
| `db.version()` | **8.0.32** (enterprise modules; maxBsonObjectSize 16 MiB; engines: wiredTiger, inMemory, devnull, queryable_wt) |
| `rs.status()` | OK — set `atlas-lfpftr-shard-0`, myState 1 (primary), 3 voting members, term 626 |
| `sh.status()` | **Unauthorized** on admin (`shardingState`, `listShards` both denied) — cannot confirm sharding; single replica-set shard name implies unsharded |
| `getParameter featureCompatibilityVersion` | **Unauthorized** (`getParameter` on admin denied) — FCV unknown |
| `listDatabases` | OK — only `mmp_rt_src`, 6,402,048 bytes (~6 MB) visible to this principal |
| `getCollectionInfos` | OK — 6 collections, all `type: collection`, no views |
| `admin.system.users` / `admin.system.roles` | **Unauthorized** — cannot enumerate other users/roles |
| `local.oplog.rs` collStats | **Unauthorized** on local — Atlas does not expose oplog to this role |
| `connectionStatus showPrivileges` | Principal `mmp_rt_source`@admin, role **`read` on `mmp_rt_src`**; actions: find, collStats, dbStats, dbHash, listCollections, listIndexes, changeStream, planCacheRead, killCursors, listSearchIndexes |

Privilege denials (admin/local/getParameter) are expected for an Atlas `read`-scoped principal and are recorded as findings, not blockers.

### Collections

| Collection | count | size (B) | storageSize (B) | nindexes | totalIndexSize (B) |
|---|---|---|---|---|---|
| users | 500 | 85,675 | 61,440 | 2 | 65,536 |
| folders | 300 | 41,688 | 53,248 | 1 | 24,576 |
| documents | 5,000 | 1,213,681 | 839,680 | 2 | 266,240 |
| comments | 12,000 | 1,613,307 | 1,019,904 | 2 | 577,536 |
| shares | 3,000 | 313,332 | 200,704 | 1 | 102,400 |
| audit_events | 20,000 | 3,383,710 | 2,060,288 | 2 | 1,130,496 |

### Indexes

| Collection | Indexes |
|---|---|
| users | `_id_`, `email_1` (email:1, **not unique**) |
| folders | `_id_` only |
| documents | `_id_`, `ownerId_1_updatedAt_-1` |
| comments | `_id_`, `documentId_1` |
| shares | `_id_` only |
| audit_events | `_id_`, `ts_1` |

No TTL, unique, partial, or text indexes. No validators, capped collections, timeseries, or views.

### Type census (field → BSON types observed)

- **users**: `_id` objectId; `createdAt` date; `displayName` string; `email` string; `role` string; `settings` object
- **folders**: `_id` objectId; `createdAt` date; `name` string; `ownerId` objectId; `parentId` null|objectId; `path` string
- **documents**: `_id` objectId; `createdAt`/`updatedAt` date; `folderId` null|objectId; `ownerId` objectId; `price` **decimal128**; `sizeBytes` int; `status` string; `tags` array; `title` string; `version` int
- **comments**: `_id`/`authorId`/`documentId` objectId; `body` string; `createdAt` date; `editedAt` date|null
- **shares**: `_id`/`documentId`/`granteeId` objectId; `expiresAt` date|null; `permission` string
- **audit_events**: `_id`/`actorId`/`targetId` objectId; `action`/`targetType` string; `meta` object; `ts` date|string (**mixed types**)

## B. Data-quality probes (counts only)

| Probe | Result |
|---|---|
| Exact counts | users 500, folders 300, documents 5,000, comments 12,000, shares 3,000, audit_events 20,000 |
| comments.documentId orphans | **15** |
| comments.authorId orphans (vs users) | 0 (field is `authorId`, not `userId`) |
| documents.folderId null / missing / orphan | 5 / 0 / 0 |
| folders.parentId null / missing / orphan | 119 / 0 / 0 |
| users distinct raw emails / distinct lowercased | 500 / 497 |
| lowercased-email dup groups / docs in them | 3 groups / 6 docs |
| audit_events.ts types | date 19,980; string 20 — all 20 strings parse via `$dateFromString` |
| shares orphans | documentId: 0; granteeId: 0 (no userId/folderId fields exist); nulls/missing: 0 |
| Doc size max / avg (B) | users 173/171; folders 189/139; documents 274/243; comments 142/134; shares 110/104; audit_events 193/169 |

Notable: `documents.price` is Decimal128 (financial field — needs explicit recon handling); `audit_events.ts` has 20 string-typed docs that all parse; 15 orphan comments; 3 case-insensitive email duplicate groups (6 docs); email index is non-unique.
