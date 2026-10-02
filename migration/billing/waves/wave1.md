# Wave 1 readiness (plan step `s4.1.0-preflight`, UNT-14)

Run branch `tp-run/mongodb-20261001T233613Z`, checked at `906fa500` (merge of
#1779). Wave 1 is unit **U1 foundation** alone (`migration/billing/units.md`,
`units/units.json#waves[0]`); its batch ticket is **UNT-15** (`s4.1.b01`), its
verify ticket UNT-16 (`s4.1.verify`). This document is the checklist the manager
ticks gate `g-preflight-1` from. It loads nothing and writes nothing: Atlas was
read (list + count) only, Oracle was not touched.

## 1. Unit U1: what the batch writes

Target database `ow_tp_billing_20261001T233613Z` on the `otterworks-demo` M0
cluster via `MONGODB_ATLAS_URI` (by name). Collections and indexes from
`migration/billing/mapping_spec.json#collections`; source tables and live rows
from `migration/billing/census.json#tables` (`COUNT(*)` at capture).

| collection | source table | live rows | `_id` | secondary indexes |
|---|---|---:|---|---|
| `codes` | `CODES` | 32 | `{codeType, codeVal}` (compound, key order fixed) | none |
| `tenants` | `TENANTS` | 69 | `TENANTS.ID` (string) | `uq_tenants_name` `{name: 1}` unique |
| `plans` | `PLANS` | 3 | `PLANS.ID` (string) | `uq_plans_code` `{code: 1}` unique |
| `subscriptions` | `SUBSCRIPTIONS` | 69 | `SUBSCRIPTIONS.ID` (string) | `ix_subscriptions_tenant_starts` `{tenantId: 1, startsOn: -1}` |
| `subscriptions_hist` | `SUBSCRIPTIONS_HIST` | 0 | `HIST_ID` (long, carried) | `ix_subscriptions_hist_subscription` `{subscriptionId: 1, _id: 1}` |

5 collections, 4 indexes, 173 live rows. Money fields (`plans.monthlyFee`,
`plans.overageRate`) are Decimal128, never double (`tolerances.json#money`).
Oracle `DATE` columns become BSON UTC datetimes; `subscriptions_hist.histDt`
keeps the verbatim `DD-MON-YY` text with a derived `histDate` only when it
parses under RR.

Code the batch touches (`units.json#units[U1].code`): `backends/mongo.py`
(new) behind `BILLING_BACKEND=mongo` in
`services/legacy-billing/app/backends/__init__.py`, `facade.py`, `app.py`, the
`mongo:7` fixture service in `docker-compose.tp.yml` and the `legacy-billing`
job of `.github/workflows/tp-golden-smoke.yml`, `Makefile`. Logic ported:
`PKG_PLANS` (`fn_list_plans`, `fn_entitlement`, `sp_change_plan`), the
`ensure_tenant` bootstrap, the `PKG_OW_UTIL` helpers including the
`billing_audit_log` writer (collection owned by U5; the helper ships here),
`TRG_SUBSCRIPTIONS_HIST` as the pre-image copy inside the `change_plan`
transaction, `TRG_SUB_NO_UNCANCEL` as a service invariant.
`SEQ_SUBSCRIPTIONS_HIST` retires.

### Fixture

`migration/billing/fixtures/demo.json` (namespace `demo`, seed `714559852`,
census sha256 `62e4c2da…2965`). U1's fixture rows: `CODES` 32, `TENANTS` 70,
`PLANS` 3, `SUBSCRIPTIONS` 70, `SUBSCRIPTIONS_HIST` 0 = 175. The +2 over the
census is the `static_seed_version` 2 pair the live host does not have
(`TENANTS` `a0000000-0000-0000-0000-000000000001`, `SUBSCRIPTIONS`
`20000000-0000-0000-0000-00000000a001`, `demo.json#census_delta`); `recon.py`
accounts for them under `census_delta.TENANTS` / `census_delta.SUBSCRIPTIONS`
and never reports them as a defect. The local Oracle fixture is
`make oracle-billing-up && make oracle-billing-seed NS=demo`; the local Mongo
fixture is `mongo:7` on `127.0.0.1:27117` (`connectivity.json#fallback`).

### Loader

`migration/billing/loaders/` does not exist on the run branch yet; UNT-15
creates it. Per the ticket: a plain python script, python-oracledb read under
`SET TRANSACTION READ ONLY` from `OW_TP_ORACLE_RO_DSN`, pymongo bulk upsert on
`_id` into `ow_tp_billing_20261001T233613Z` only, idempotent, so the parallel
run can reuse it for delta loads. It must produce exactly what
`recon.py`'s reference mapping produces (`load_documents` in
`migration/billing/recon/recon.py`): camelCase fields, the compound `_id` for
`codes`, Decimal128 money, the four indexes above.

## 2. Atlas is empty for U1 (read-only check)

`mongosh "$MONGODB_ATLAS_URI"` against `ow_tp_billing_20261001T233613Z`,
`getCollectionNames()` + `countDocuments({})` per U1 collection, 2026-10-02:

```
database: ow_tp_billing_20261001T233613Z
collections present: []
codes: absent
tenants: absent
plans: absent
subscriptions: absent
subscriptions_hist: absent
principal: [{"user":"otterworks-app","db":"admin"}]
```

The migration database has no collections at all (UNT-4's
`_connectivity_probe` was dropped after its probe). No write, drop or index
change was issued anywhere.

## 3. `recon.py` on the fixture, U1 collections only

`migration/billing/waves/wave1/fixture_recon.py` drives `recon.py` the way its
self-test does (faithful synthetic copy of `demo.json` loaded through the
mapping into a loopback `mongo:7`), restricted to U1's five collections:

```sh
docker run -d --rm --name ow-billing-mongo -p 27117:27017 mongo:7
uv run --no-project --with pymongo==4.10.1 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
  python3 migration/billing/waves/wave1/fixture_recon.py --unit U1 --mongo-uri mongodb://127.0.0.1:27117
make tp-validate-recon FILE=migration/billing/waves/wave1/U1.fixture.recon.json
```

```
U1: 5 collections ['codes', 'tenants', 'plans', 'subscriptions', 'subscriptions_hist']; synthetic copy 175 rows in ['CODES', 'PLANS', 'SUBSCRIPTIONS', 'SUBSCRIPTIONS_HIST', 'TENANTS'] -> 175 documents
recon fixture: verdict=fail checks=38 failed=['anomalies.orphaned_rows.source', 'anomalies.orphaned_rows.target', 'anomalies.dirty_dates.source', 'anomalies.dirty_dates.target', 'anomalies.malformed_csv_lists.source', 'anomalies.malformed_csv_lists.target'] -> migration/billing/waves/wave1/U1.fixture.recon.json
merge_evidence=False (fixture/local result: never merge evidence (tolerances.json#source.mode is live))

validated 1 recon file(s)
PASS
```

Report: `migration/billing/waves/wave1/U1.fixture.recon.json` (`run_mode:
fixture`, `merge_evidence: false`, validates against
`recon-report.schema.json`). All 32 U1 checks pass: `row_count`,
`keyed_presence`, `keyed_values`, `money_decimal128`,
`fields_outside_mapping` for each of the five collections, both
`census_delta.*` checks and `derived_fields.rules`.

**Finding for UNT-15 (not fixed here; the manager decides where):** the 6
failed checks are the planted-anomaly set compares for `INVOICE_LINE`
(`orphaned_rows`) and `CUSTOMER_MASTER` (`dirty_dates`,
`malformed_csv_lists`), tables that belong to U4 and U2. `ReconRun` honours
the `--collections` subset for every per-collection check but
`_check_anomaly_sets` still evaluates every kind in `demo.json#anomalies`, so
with the tables unfetched it sees `size: 0` against the planted 37/50/31 and
fails. The same will happen to UNT-15's live run
(`recon.py run --mode live --collections codes,tenants,plans,subscriptions,subscriptions_hist`)
until either (a) `recon.py` skips anomaly kinds whose target table is outside
the run's collections and lists them under `unverified_paths` (a small change
in `_check_anomaly_sets`, owed by whoever the manager names), or (b) the
wave-1 acceptance reads "all U1 collection checks pass; anomaly checks for
out-of-scope tables are expected `fail` until wave 2". Option (a) keeps the
verdict meaningful and is the recommendation.

## 4. UNT-15 has nothing outstanding

- Open human decisions (`units.json#decisions.open`, `units.md` "Open human
  decisions"): `bd-overdue-status-owner` is U5; `d-cdc-connector` and
  `d-mainframe-load` are cutover. None touches U1.
- Decision in force: `d-logic-home` (Mongo backend in the facade) applied.
- Dependencies on the run branch at `906fa500`: `units.md` + `units/units.json`
  (#1777, `g-model-accepted` ticked), `mapping_spec.json` (#1775, #1776),
  `tolerances.json`, `fixtures/demo.json`, `recon/recon.py` + README (#1778),
  `connectivity.json` PASS (#1779), Atlas scope decision (#1769). Board: UNT-15
  is blocked only by UNT-14 (this ticket); UNT-4, UNT-12, UNT-13 are Done.
- Cross-unit edges into U1 are all "satisfied by wave 1"; the one edge out of
  U1 (`GET /me.customer` reads `customers`) is deferred to wave 2 and its
  parity is a UNT-22 check, not a U1 one.

## Acceptance for UNT-15 (what the manager merges on)

1. One PR into `tp-run/mongodb-20261001T233613Z`, review budget 2 rounds,
   `make tp-smoke` green on both `BILLING_BACKEND=oracle` and `mongo` (the
   golden path stays self-contained: `mongo:7` is a fixture container, never
   Atlas).
2. A **live** recon report committed under `migration/billing/recon/out/`
   (or the unit's own directory), produced by
   `recon.py run --mode live` against `OW_TP_ORACLE_RO_DSN` and
   `MONGODB_ATLAS_URI` / `ow_tp_billing_20261001T233613Z` with
   `--collections codes,tenants,plans,subscriptions,subscriptions_hist`, that
   validates with `make tp-validate-recon FILE=<report>` and passes under
   `tolerances.json` (exact match, row diff 0, Decimal128 money, no float):
   `run_mode: live`, `verdict: pass`, `merge_evidence: true`,
   `idempotency_rerun.result: pass`. The fixture report in this directory is
   never merge evidence. The anomaly-scope finding in section 3 must be
   resolved for `verdict: pass` to be reachable.
3. Loader under `migration/billing/loaders/` as described above; a rerun must
   be a no-op (upsert on `_id`), proven by running it twice before the live
   recon.
4. Route parity for the plans module on `BILLING_BACKEND=oracle` vs
   `BILLING_BACKEND=mongo`: the 5 procs scenarios `procs/scenarios/plans/001-005.yaml`
   (`fn_list_plans`, `fn_entitlement`, `sp_change_plan`) replayed against the
   Mongo backend produce the same result fields and state probes as the
   immutable transcripts `procs/transcripts/plans/PLANS-001..005.json`
   (`make procs-parity`/`procs/harness/replay.py` with the Mongo backend, or
   the equivalent recorded through the facade routes
   `GET /api/v1/billing/plans`, `GET /api/v1/billing/entitlement`,
   `POST /api/v1/billing/plan-change` and the legacy `/plans*` routes). The
   `customer` key of `GET /api/v1/billing/me` is null on Mongo until U2 and is
   excluded from this check.
5. `python3 migration/billing/units/check.py` and
   `python3 migration/billing/mapping/build_mapping_spec.py --check` still
   green; no change to `tolerances.json` or `mapping_spec.json` without a plan
   decision.
