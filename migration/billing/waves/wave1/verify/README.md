# Wave 1 (U1) independent verification — UNT-16

Verified: PR #1782 at head `1dd952916e32fd7d1868b31d9cf67233e78ac558` (before merge), by a
session that migrated none of it. Oracle `OW_BILLING` read-only (`SET TRANSACTION READ ONLY`);
Atlas reads only, database `ow_tp_billing_20261001T233613Z`; secrets by name
(`OW_TP_ORACLE_RO_DSN`, `MONGODB_ATLAS_URI`).

| Axis | Result | Evidence |
|---|---|---|
| Live recon, `--collections codes,tenants,plans,subscriptions,subscriptions_hist` | **PASS** 30/30, `merge_evidence=true`, idempotency rerun pass, schema-valid (`make tp-validate-recon`) | `U1.verify.live.recon.json`, `.log` |
| Four anomaly kinds (`dirty_dates`, `eav_boolean_spellings`, `malformed_csv_lists`, `orphaned_rows`) | listed under `unverified_paths` ("outside this run's collections; not evaluated"), **not** counted as pass | `U1.verify.live.recon.json#unverified_paths` |
| Atlas read-only probe (counts 32/69/3/69/0, indexes, principal, orphan joins = 0, Decimal128 money) | PASS | `U1.verify.atlas_probe.log` |
| Plans route parity PLANS-001..005 + U1 facade routes + non-U1 Mongo routes → 501 | PASS (fixture only, `merge_evidence=false`) | `U1.verify.plans_parity.json`, `.log` |
| Edge probes EDGE-001..012 (fixture only, `merge_evidence=false`) | 9/12 pass; **EDGE-005 / EDGE-011 / EDGE-012 fail** (findings below) | `U1.verify.edge_probes.json`, `.log`, `U1.verify.local_edge.recon.json` |

## Findings (fixture-reproduced, outside the recon gate)

1. **Same-day plan change diverges (EDGE-005, EDGE-011).** `backends/oracle.change_plan`
   (commit 217a062d "Fix same-day billing plan changes") first closes open subscriptions with
   `starts_on = effective_on` (`ends_on = effective_on - 1`, cancelled kept) before
   `PKG_PLANS.sp_change_plan`; `backends/mongo.change_plan` only closes `startsOn < effective_on`.
   Reachable through the public facade: `GET /api/v1/billing/me` (bootstraps today) then
   `POST /api/v1/billing/plan-change` effective today → Oracle: one open subscription,
   entitlement GROWTH, one hist row; Mongo: two open subscriptions, entitlement STARTER, no hist
   row. `tests/test_mongo.py::test_change_plan_same_day_leaves_same_day_subscription_open`
   codifies the divergent behaviour.
2. **Carried `subscriptions_hist` rows get no `histDate` (EDGE-012).** `TRG_SUBSCRIPTIONS_HIST`
   writes `HIST_DT` as `DD-MON-YY HH24:MI:SS`; `recon.parse_ddmonyy` / the loader's derived rule
   accept `^DD-MON-YY$` only, so every trigger-written row loads without `histDate` and recon
   accepts that as correct. The app's own `f_str2dt` accepts the suffix, so app-written hist rows
   do get `histDate`. Vacuous for this merge (live `subscriptions_hist` = 0 rows) but a shape
   inconsistency for parallel run / cutover.

## Rerun

```sh
uv run --no-project --with pymongo==4.10.1 --with oracledb==2.5.1 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
  python3 migration/billing/recon/recon.py run --mode live \
  --collections codes,tenants,plans,subscriptions,subscriptions_hist \
  --out migration/billing/waves/wave1/verify/U1.verify.live.recon.json
make tp-validate-recon FILE=migration/billing/waves/wave1/verify/U1.verify.live.recon.json
make oracle-billing-up && make oracle-billing-seed NS=demo && make mongo-billing-up
make tp-u1-parity REPORT=$PWD/migration/billing/waves/wave1/verify/U1.verify.plans_parity.json
TZ=UTC LC_ALL=C OW_TP_ORACLE_FIXTURE_DSN='ow_billing/ow_billing@localhost:52521/FREEPDB1' \
  OW_TP_MONGO_FIXTURE_URI='mongodb://127.0.0.1:27117/?directConnection=true' \
  uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with flask==3.1.1 --with pyyaml==6.0.2 \
  --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
  python3 migration/billing/waves/wave1/verify/edge_probes.py --repo-root <checkout of the PR head>
```

`edge_probes.py` refuses non-loopback Oracle/Mongo endpoints (via `plans_parity.Fixture`) and
mutates only the local fixture (it disables `TRG_SUB_NO_UNCANCEL` on the fixture for one baseline
restore, never live).
