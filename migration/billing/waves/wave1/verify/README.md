# Wave 1 (U1) independent verification — UNT-16

Verified: PR #1782 at head `86c634aeab3ddc6bcf738bfc3d9d48312913bdd0` (before merge; first pass at
`1dd952916e32fd7d1868b31d9cf67233e78ac558`, re-verified after the same-day fix 779515b9), by a
session that migrated none of it. Oracle `OW_BILLING` read-only (`SET TRANSACTION READ ONLY`);
Atlas reads only, database `ow_tp_billing_20261001T233613Z`; secrets by name
(`OW_TP_ORACLE_RO_DSN`, `MONGODB_ATLAS_URI`).

| Axis | Result | Evidence |
|---|---|---|
| Live recon, `--collections codes,tenants,plans,subscriptions,subscriptions_hist` | **PASS** 30/30, `merge_evidence=true`, idempotency rerun pass, schema-valid (`make tp-validate-recon`) | `U1.verify.live.recon.json`, `.log` |
| Four anomaly kinds (`dirty_dates`, `eav_boolean_spellings`, `malformed_csv_lists`, `orphaned_rows`) | listed under `unverified_paths` ("outside this run's collections; not evaluated"), **not** counted as pass | `U1.verify.live.recon.json#unverified_paths` |
| Atlas read-only probe (counts 32/69/3/69/0, indexes, principal, orphan joins = 0, Decimal128 money) | PASS | `U1.verify.atlas_probe.log` |
| Plans route parity PLANS-001..005 + U1 facade routes + non-U1 Mongo routes → 501 | PASS (fixture only, `merge_evidence=false`) | `U1.verify.plans_parity.json`, `.log` |
| Edge probes EDGE-001..013 (fixture only, `merge_evidence=false`) | 12/13 pass at 86c634ae; **EDGE-012 fails** (finding 2, tracked as UNT-34). At 1dd95291 it was 9/12 with EDGE-005 / EDGE-011 failing (finding 1, fixed by 779515b9) | `U1.verify.edge_probes.json`, `.log`, `U1.verify.local_edge.recon.json` |

**Final per-batch verdict (U1, the only wave-1 batch): PASS on the merge-evidence axes at 86c634ae.**
Live recon was not re-run for 86c634ae: `git diff 1dd95291..86c634ae -- migration/billing/loaders
migration/billing/recon migration/billing/mapping_spec.json migration/billing/tolerances.json` is
empty (only `backends/mongo.py`, `tests/test_mongo.py`, `plans_parity.py` and wave-1 evidence changed),
so the live report at 1dd95291 stands for the loader/recon code under merge.

## Findings (fixture-reproduced, outside the recon gate)

1. **Same-day plan change diverges (EDGE-005, EDGE-011) — fixed in 779515b9, re-verified pass.**
   At 1dd95291: `backends/oracle.change_plan`
   (commit 217a062d "Fix same-day billing plan changes") first closes open subscriptions with
   `starts_on = effective_on` (`ends_on = effective_on - 1`, cancelled kept) before
   `PKG_PLANS.sp_change_plan`; `backends/mongo.change_plan` only closes `startsOn < effective_on`.
   Reachable through the public facade: `GET /api/v1/billing/me` (bootstraps today) then
   `POST /api/v1/billing/plan-change` effective today → Oracle: one open subscription,
   entitlement GROWTH, one hist row; Mongo: two open subscriptions, entitlement STARTER, no hist
   row. `tests/test_mongo.py::test_change_plan_same_day_leaves_same_day_subscription_open`
   codified the divergent behaviour. 779515b9 closes `startsOn = eff` first, then `startsOn < eff`,
   inside the same transaction, and the test now asserts the Oracle shape; at 86c634ae EDGE-005 and
   EDGE-011 pass (one open subscription, entitlement GROWTH, one hist pre-image on both backends).
2. **Carried `subscriptions_hist` rows get no `histDate` (EDGE-012).** `TRG_SUBSCRIPTIONS_HIST`
   writes `HIST_DT` as `DD-MON-YY HH24:MI:SS`; `recon.parse_ddmonyy` / the loader's derived rule
   accept `^DD-MON-YY$` only, so every trigger-written row loads without `histDate` and recon
   accepts that as correct. The app's own `f_str2dt` accepts the suffix, so app-written hist rows
   do get `histDate`. Vacuous for this merge (live `subscriptions_hist` = 0 rows) but a shape
   inconsistency for parallel run / cutover.

3. **`Fixture.probe` ordering change (86c634ae) judged — hides nothing (EDGE-013).** `plans_parity.py`
   now sorts subscription rows by `(starts_on, closed-before-open, ends_on, plan_id)` on both estates
   instead of `ORDER BY starts_on` / `sort(startsOn)`, whose tie order on equal `starts_on` was
   engine-specific (the same-day case produces exactly such a tie). EDGE-013 checks, on every static
   tenant after same-day and PLANS-005-style changes, that the sorted probe is a permutation of the
   raw rows read independently (`SELECT ... FROM subscriptions` / `find({tenantId})`, no sort) and
   that probe equality coincides with multiset equality of `(plan_id, starts_on, ends_on, status)`:
   pass on both backends. Caveat recorded in the probe notes: the sort key omits `status`, so two rows
   equal on the four key fields but differing in status would keep input order; the deterministic
   md5 subscription id (tenant+plan+effective) makes that unreachable through `change_plan`.

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
