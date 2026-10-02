# Wave 2 independent verification (UNT-22)

Evidence for `g-recon-pass-2` and `g-independent-verify-2`, produced by a session that migrated none of
wave 2, on the run branch `tp-run/mongodb-20261001T233613Z`. Each batch PR was verified at the head SHA
recorded in its report, before the manager merged it. Live reports read Atlas database
`ow_tp_billing_20261001T233613Z` read-only (secrets by name: `MONGODB_ATLAS_URI`, `OW_TP_ORACLE_RO_DSN`);
everything that writes ran on the local fixtures only (`make oracle-billing-up`, `make tp-mongo-up`).

| Unit | PR | Head verified | Live recon | Parity | Edge probes | Verdict |
|------|----|---------------|------------|--------|-------------|---------|
| U2 customers (`customers,customers_hist`) | #1786 | `ad18ed0410b7b7a32de9f45467bdab9d84906d16` | pass, 28/28, merge_evidence true | customer parity pass | 12/12 | PASS |
| U3 usage + rating (`rating_periods,usage_events`) | #1788 | `5dd059d3369c25ffe38f9db0442f9960e7f0bcb5` | pass, 20/20, merge_evidence true | RATING-001..008 pass | 10/11 (EDGE-U3-007 divergence) | PASS on merge-evidence axes; one behavioural divergence reported |
| U3 rebased onto run branch (incl. U2) | #1788 | `3843e73141fd0c69a992f64195906074d74699cd` | fixture recon pass 20/20; live recon + loader-vs-Atlas pending (live Oracle host unreachable at run time) | RATING-001..008 pass, U2 customer parity pass | 10/11 identical, EDGE-U3-007 accepted (d-refinalize-seeded-period) | pending the two live axes |

## Per-batch procedure

1. `recon.py run --mode live --collections <unit>` from the PR head checkout, `make tp-validate-recon FILE=...`
   PASS, then check ids / counts / anomaly sets / idempotency compared with the batch's committed report
   (`migration/billing/recon/out/U<n>.live.recon.json`).
2. Route parity on the fixture with the batch's own parity tool (`make tp-u2-parity`, `make tp-u3-parity`),
   `BILLING_BACKEND=oracle` vs `mongo`.
3. Edge probes past the gate (`u<n>_edge_probes.py`, fixture only, `merge_evidence: false`).
4. Scope: `recon.py`, `tolerances.json`, `mapping_spec.json` unchanged on the PR; loader writes only the unit's
   collections in the target database; backend routes write nothing outside the unit (plus `log_msg` audit rows).

## U2 (#1786)

- `U2.verify.live.recon.json`: 28/28, idempotency pass. 25000 customers, 8333 embedded attributes, 0 hist;
  anomaly sets (dirty dates, malformed CSV) equal to the committed report.
- `U2.verify.customer_parity.json`: 4 tenants + 50 dirty-date / 31 malformed-CSV rows identical on both backends.
- `U2.verify.edge_probes.json` (`u2_edge_probes.py`): EDGE-U2-001..012 pass: empty / unknown tenant, anomalies
  through the facade, `TRG_CUSTOMER_MASTER_HIST` pre-images carried and recomputed on update, update atomicity
  (customer unchanged when the pre-image insert is rejected), money edges, EAV outside the contract, insert-trigger
  derivations, write scope. Note (not a defect): a non-CUSTOMER or orphan EAV row fails the whole load (no
  quarantine in U2).

## U3 (#1788)

- `U3.verify.live.recon.json`: 20/20, idempotency pass. 814 usage_events, 3 rating_periods, 3 embedded results;
  ids and summary equal to the committed report.
- `U3.verify.rating_parity.json`: RATING-001..008 ok on both, facade usage/ingest snapshot identical, duplicate
  internal event -> `duplicate` on both.
- `U3.verify.edge_probes.json` (`u3_edge_probes.py`): day-string window edges, `ADD_MONTHS` month-end rollover
  window, ROUND half-away-from-zero on money and on the suspension proration, NUMBER(12,6) rates, finalize
  atomicity with the autonomous `log_msg` row surviving the rollback, re-finalise of a module-created period,
  `TRG_USAGE_EVENTS_CHECK` equivalents and a USAGE_KIND outside the DECODE, loader embedding + local recon with
  edge rows, write scope.
- **EDGE-U3-007 divergence** (reported to the manager, batch code untouched): re-finalising a period whose id is not
  `f_md5_uuid(tenant || period_start)` (all 3 live rows are hand-seeded `40000000-...` ids). Oracle
  `sp_finalize_rating` falls back to the UPDATE on `DUP_VAL_ON_INDEX` but then inserts `rating_results` with the
  recomputed md5 period id -> ORA-02291, nothing changes, HTTP 500. The port finalises by the existing document's
  `_id`, recomputes the embedded result in place and returns 200. Repro:
  `POST /api/rating/finalize {"tenant_id": "00000000-0000-0000-0000-000000000001", "period_start": "2026-01-01", "period_end": "2026-01-31"}`
  on each backend after `make tp-u3-load`.
- Note for U2+U3 merged trees: `rating_parity.py` asserts `/api/v1/billing/customer` returns 501 on mongo, which
  is true only before U2 lands. Resolved by the rebase below (the probe now targets the still-unported
  `/invoices` and `/admin/dunning` routes).
- Manager ruling: EDGE-U3-007 is keep-port, listed as a behavior difference under plan decision
  `d-refinalize-seeded-period`; it does not block U3.

### U3 rebased head `3843e73141fd0c69a992f64195906074d74699cd` (delta from `5dd059d3`)

Diff review: `app/backends/mongo.py`, `app/facade.py`, `tests/test_facade.py`, `tests/test_mongo.py` carry the same
U3 hunks (offsets only, now layered over U2); `rating_parity.py` drops the stale `/customer` 501 probe; the U3-specific
`loaders/oracle_to_mongo.py#build_documents` is replaced by U2's generalised one, so `rating_periods.result` is now
embedded through `recon.load_documents`. `recon.py`, `tolerances.json`, `mapping_spec.json` unchanged.

- `U3r.verify.u3_load.json` + `U3r.verify.fixture.recon.json`: `make tp-u3-load` through the new loader (817
  usage_events, 3 rating_periods with 3 embedded results, pass 2 no-op) then `recon.py run --mode local` 20/20,
  validates; check ids, results and anomaly sets identical to the worker's `U3.fixture.recon.json`.
- `U3r.verify.rating_parity.json`: RATING-001..008 pass on both backends; `/invoices`, `/admin/dunning` 501 on mongo.
- `U3r.verify.customer_parity.json` (`make tp-u2-parity`): U2's customer path still passes at this head
  (4 tenants, 50/50 dirty-date, 31/31 malformed-CSV rows identical).
- `U3r.verify.edge_probes.json`: 10/11 identical; EDGE-U3-007 recorded as `accepted_behavior_difference`
  (`--accept EDGE-U3-007=d-refinalize-seeded-period`), `blocking_failures: []`.
- pytest (`services/legacy-billing`, fixture Mongo set): 78 passed.
- `loader_vs_atlas.py`: read-only comparison of the head's loader output (built from the live Oracle read-only
  principal) against the documents already in Atlas for `rating_periods` (incl. embedded `result`) and
  `usage_events`; `find()` only, no writes. Result file `U3r.verify.loader_vs_atlas.json` once the live Oracle host
  answers again (TCP connect timed out from ~19:15Z on 2026-10-02); same for the fresh live recon
  `U3r.verify.live.recon.json`.

## Re-running

```sh
make tp-u3-parity REPORT=/tmp/U3.rating_parity.json
TZ=UTC LC_ALL=C OW_TP_ORACLE_FIXTURE_DSN=... OW_TP_MONGO_FIXTURE_URI=... \
  uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with flask==3.1.1 \
    --with pyyaml==6.0.2 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
    python3 migration/billing/waves/wave2/verify/u3_edge_probes.py --repo-root <PR checkout> \
      --accept EDGE-U3-007=d-refinalize-seeded-period
uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with jsonschema==4.25.1 \
  --with rfc3339-validator==0.1.4 \
  python3 migration/billing/waves/wave2/verify/loader_vs_atlas.py --repo-root <PR checkout> \
    --collections rating_periods,usage_events --out /tmp/U3.loader_vs_atlas.json
```
