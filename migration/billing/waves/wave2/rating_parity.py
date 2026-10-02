#!/usr/bin/env python3
"""U3 route parity: usage + rating module on BILLING_BACKEND=oracle vs BILLING_BACKEND=mongo.

Replays procs/scenarios/rating/001-008.yaml (fn_usage_rating, fn_usage_summary,
sp_finalize_rating) through the legacy-billing Flask app in-process, once per backend, and
grades both against the immutable transcripts procs/transcripts/rating/RATING-00N.json
(business fields + the rating_result probe). Before every scenario the Oracle fixture's static
tenants are reset to the checked-in seed (wave1 plans_parity.Fixture for subscriptions, plus
the rating periods/results and usage events this module writes) and the Mongo fixture is
reloaded from it with migration/billing/loaders/oracle_to_mongo.py, so both backends start
from the same rows. A second section records the /api/v1/billing/usage facade and the
/internal/usage/events ingestion (the bridge's only write path) on both backends and requires
them to be identical.

Fixture only: requires `make oracle-billing-up` and `make mongo-billing-up`; never Atlas.

    make tp-u3-parity        # -> migration/billing/waves/wave2/U3.rating_parity.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "migration" / "billing" / "waves" / "wave1"))

import plans_parity  # noqa: E402  (U1 fixture reset, transcript grading)

SCENARIOS = ROOT / "procs" / "scenarios" / "rating"
TRANSCRIPTS = ROOT / "procs" / "transcripts" / "rating"
U3 = ["usage_events", "rating_periods"]
TENANT = plans_parity.TENANT
PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}
NEW_EVENT = {
    "event_id": "30000000-0000-0000-0000-00000000feed", "tenant_id": TENANT, "email": "tenant-one@example.com",
    "kind": "storage", "units": 7, "occurred_at": "2026-02-20T12:00:00Z",
}
INTERNAL_TOKEN = "rating-parity"


def _seed_ids(statements, table):
    ids = []
    for statement in statements:
        m = re.match(rf"INSERT INTO {table} \(([^)]*)\) VALUES \((.*)\)$", statement, re.I | re.S)
        if m:
            cols = [c.strip() for c in m.group(1).split(",")]
            vals = [v.strip() for v in m.group(2).split(",")]
            ids.append(vals[cols.index("id")])
    return ids


class Fixture(plans_parity.Fixture):
    def reset(self):
        """Rating-module baseline on top of the plans one: static tenants' usage events, rating
        periods and results back to 03_seed_static.sql (rows the module wrote are deleted; the
        seeded ones are never modified by the scenarios), then U3 reloaded into the mongo fixture."""
        import oracledb

        super().reset()
        ids = ", ".join(f"'{t}'" for t in self.oracle_record.STATIC_TENANTS)
        statements = list(self.oracle_record.seed_statements())
        periods = ", ".join(_seed_ids(statements, "rating_periods"))
        events = ", ".join(_seed_ids(statements, "usage_events"))
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM rating_results WHERE period_id IN "
                f"(SELECT id FROM rating_periods WHERE tenant_id IN ({ids}) AND id NOT IN ({periods}))")
            cur.execute(f"DELETE FROM rating_periods WHERE tenant_id IN ({ids}) AND id NOT IN ({periods})")
            cur.execute(f"DELETE FROM usage_events WHERE tenant_id IN ({ids}) AND id NOT IN ({events})")
            conn.commit()
        for name in U3:
            self.mongo[self.database].drop_collection(name)
        rc = self.loader.main([
            "--mode", "fixture", "--collections", ",".join(U3),
            "--oracle-dsn-env", self.oracle_dsn_env, "--mongo-uri-env", self.mongo_uri_env,
            "--mongo-db", self.database,
        ])
        if rc != 0:
            raise SystemExit("fixture reload failed")

    def probe_oracle(self, tenant_id, period_start):
        import oracledb

        oracledb.defaults.fetch_decimals = True
        with oracledb.connect(**self.dsn_kw) as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT rr.used_units, rr.quota_units, rr.rollover_units, rr.billable_units, rr.overage_amount
                     FROM rating_results rr JOIN rating_periods rp ON rp.id = rr.period_id
                    WHERE rp.tenant_id = :1 AND rp.period_start = :2""",
                (tenant_id, dt.date.fromisoformat(period_start)),
            )
            return [_result_row(*r) for r in cur.fetchall()]

    def probe_mongo(self, tenant_id, period_start):
        start = dt.datetime.fromisoformat(period_start).replace(tzinfo=dt.timezone.utc)
        docs = self.mongo[self.database].rating_periods.find({"tenantId": tenant_id, "periodStart": start})
        return [
            _result_row(r["usedUnits"], r["quotaUnits"], r["rolloverUnits"], r["billableUnits"], r["overageAmount"].to_decimal())
            for r in (d["result"] for d in docs if "result" in d)
        ]

    def probe(self, backend, tenant_id, period_start):
        return self.probe_oracle(tenant_id, period_start) if backend == "oracle" else self.probe_mongo(tenant_id, period_start)


def _result_row(used, quota, rollover, billable, overage):
    """The rating_result probe as the transcripts hold it (`overage_amount::text` of a NUMERIC(12,2))."""
    return {"used_units": int(used), "quota_units": int(quota), "rollover_units": int(rollover),
            "billable_units": int(billable), "overage_amount": str(Decimal(overage).quantize(Decimal("0.01")))}


def run_scenario(client, fixture, backend, scenario):
    inputs = {i["name"]: str(i["value"]) for i in scenario.get("inputs", [])}
    entry = scenario["entrypoint"]
    body = {"tenant_id": inputs["tenant_id"], "period_start": inputs["period_start"], "period_end": inputs["period_end"]}
    if entry == "billing.fn_usage_rating":
        rows = client.post("/api/rating/preview", json=body).get_json()
    elif entry == "billing.fn_usage_summary":
        resp = client.get("/api/v1/billing/usage", headers={"X-User-ID": inputs["tenant_id"]},
                          query_string={"period_start": inputs["period_start"], "period_end": inputs["period_end"]})
        rows = resp.get_json()["summary"]
    elif entry == "billing.sp_finalize_rating":
        resp = client.post("/api/rating/finalize", json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"{scenario['id']} on {backend}: HTTP {resp.status_code}")
        rows = fixture.probe(backend, inputs["tenant_id"], inputs["period_start"])
    else:
        raise RuntimeError(f"unknown entrypoint {entry}")
    fields = plans_parity.capture(rows, scenario["fields"])
    probes = {p["id"]: fixture.probe(backend, inputs["tenant_id"], inputs["period_start"]) for p in scenario.get("probes", [])}
    return fields, probes


def facade_snapshot(client):
    headers = {"X-User-ID": TENANT, "X-User-Email": "tenant-one@example.com"}
    internal = {"X-Internal-Token": INTERNAL_TOKEN}
    before = client.get("/api/v1/billing/usage", query_string=PERIOD, headers=headers).get_json()
    first = client.post("/internal/usage/events", json=NEW_EVENT, headers=internal)
    again = client.post("/internal/usage/events", json=NEW_EVENT, headers=internal)
    after = client.get("/api/v1/billing/usage", query_string=PERIOD, headers=headers).get_json()
    preview = client.post("/api/rating/preview", json={"tenant_id": TENANT, **PERIOD})
    return {
        "GET /api/v1/billing/usage?period_start=2026-02-01&period_end=2026-02-28": before,
        "POST /internal/usage/events (bridge write path)": {"status": first.status_code, "body": first.get_json()},
        "POST /internal/usage/events (same event again)": {"status": again.status_code, "body": again.get_json()},
        "GET /api/v1/billing/usage after the ingest": after,
        "POST /api/rating/preview": {"status": preview.status_code, "body": preview.get_json()},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_FIXTURE_DSN")
    p.add_argument("--mongo-uri-env", default="OW_TP_MONGO_FIXTURE_URI")
    p.add_argument("--out", default=str(HERE / "U3.rating_parity.json"))
    args = p.parse_args(argv)

    os.environ["MONGODB_ATLAS_URI"] = os.environ[args.mongo_uri_env]  # process-local: the fixture mongod
    os.environ["USAGE_INTERNAL_TOKEN"] = INTERNAL_TOKEN
    os.environ.setdefault("ORACLE_PORT", "52521")
    fixture = Fixture(args.oracle_dsn_env, args.mongo_uri_env)
    from app import app

    scenarios = [yaml.safe_load(path.read_text()) for path in sorted(SCENARIOS.glob("*.yaml"))]
    report = {
        "kind": "rating-parity", "unit": "U3", "run_mode": "fixture", "merge_evidence": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"oracle": f"local fixture {fixture.oracle_host}", "mongo": f"local fixture, database {fixture.database}"},
        "transcripts": "procs/transcripts/rating/RATING-001..008.json (immutable)",
        "scenarios": [], "facade": {}, "verdict": "pass",
    }
    for scenario in scenarios:
        transcript = json.loads((TRANSCRIPTS / f"{scenario['id']}.json").read_text())
        entry = {"id": scenario["id"], "entrypoint": scenario["entrypoint"], "description": scenario["description"],
                 "expected": {"business_fields": transcript["business_fields"], "probes": transcript["probes"]}, "backends": {}}
        for backend in ("oracle", "mongo"):
            fixture.reset()
            os.environ["BILLING_BACKEND"] = backend
            fields, probes = run_scenario(app.test_client(), fixture, backend, scenario)
            entry["backends"][backend] = {
                "business_fields": fields, "probes": probes,
                "fields_match": fields == transcript["business_fields"], "probes_match": probes == transcript["probes"],
            }
        entry["pass"] = all(b["fields_match"] and b["probes_match"] for b in entry["backends"].values()) and (
            entry["backends"]["oracle"]["business_fields"] == entry["backends"]["mongo"]["business_fields"])
        if not entry["pass"]:
            report["verdict"] = "fail"
        report["scenarios"].append(entry)
        print(f"{scenario['id']}: oracle={'ok' if entry['backends']['oracle']['fields_match'] else 'MISMATCH'} "
              f"mongo={'ok' if entry['backends']['mongo']['fields_match'] else 'MISMATCH'} -> {'pass' if entry['pass'] else 'FAIL'}")

    for backend in ("oracle", "mongo"):
        fixture.reset()
        os.environ["BILLING_BACKEND"] = backend
        report["facade"][backend] = facade_snapshot(app.test_client())
    report["facade"]["identical"] = report["facade"]["oracle"] == report["facade"]["mongo"]
    if not report["facade"]["identical"]:
        report["verdict"] = "fail"
    print(f"facade U3 routes identical on both backends: {report['facade']['identical']}")
    fixture.reset()

    out = Path(args.out)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"rating parity {report['verdict']} -> {out}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
