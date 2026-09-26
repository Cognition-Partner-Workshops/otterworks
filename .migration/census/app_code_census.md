# App Code Census — Mongo surface in `frontend/` and `services/collab-service`

Branch: `tp-run/mongodb-20260926T170458Z-rt-fanout`. Repo read-only scan.

## Driver usage

- No `"mongodb"` or `"mongoose"` dependency in any `package.json` repo-wide (`rg -l '"mongodb"|"mongoose"' --glob package.json` → no hits), and none in the collab-service or frontend lockfiles.
- `rg -n '\$where|mapReduce|\beval\(' frontend services/collab-service` (excluding node_modules) → **no hits**. No server-side JS execution in scope.

## Mongo / collection-name references

`rg -l "mmp_rt|mongodb" frontend services/collab-service` → only two hits, both cosmetic:

- `frontend/admin-dashboard/src/app/core/models/billing-report.model.ts:2` — `engine: 'oracle' | 'mongodb' | string` on a billing-report source model.
- `frontend/admin-dashboard/src/app/pages/billing-report/billing-report.component.ts:29,230,358` — renders an icon/color badge and the label "MongoDB Atlas" when `report.source.engine === 'mongodb'`.

Both are display-only plumbing for a billing report's source-engine badge; they issue no Mongo traffic and hold no connection code. Literal collection names (`users`, `folders`, `documents`, `comments`, `shares`, `audit_events`, `mmp_rt`) appear in UI components only as generic domain words (document-card.tsx, share-dialog.tsx, api.ts, etc.) — no DB access.

## collab-service data layer today

`services/collab-service` is a Node/TypeScript service (`src/index.ts`, `src/config.ts`, `src/handlers/collaboration.ts`). It has **no MongoDB connection code at all** — no `mongodb`/`mongoose` imports, no Mongo env vars. Its only datastore is Redis, configured via env vars: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`, `REDIS_KEY_PREFIX` (default `collab:`), plus doc/snapshot TTL knobs (`DOC_TTL_SECONDS`, `SNAPSHOT_TTL_SECONDS`, `PERSIST_INTERVAL_MS`, `SNAPSHOT_INTERVAL_MS`, `MAX_SNAPSHOTS`). Auth env: `JWT_SECRET`, `JWT_ISSUER`.

Implication: the `mmp_rt_src` MongoDB estate is not wired to any code in this repo's collab-service or frontends; it appears to be a standalone legacy store for the migration demo.
