"""Unit u-01-tenancy loader: TENANTS, PLANS, SUBSCRIPTIONS, SUBSCRIPTIONS_HIST ->
ow_billing_migration.{tenants,plans,subscriptions,subscriptionsHist}.

Mapping: .migration/03_mapping_spec.json (map-draft-2); decisions cited there
(code_lookup: numeric *_CD kept verbatim; SUBSCRIPTIONS_HIST is a history_copy collection
keyed by HIST_ID with HIST_DT parsed as 'DD-MON-YY HH24:MI:SS').

Usage (from the repo root, offline):
  env -u MONGODB_ATLAS_URI python services/legacy-billing/migration/mongo/load_tenancy.py \
      --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGO_LOCAL_URI \
      --target-db ow_billing_migration --quarantine-out <dir>
"""

import argparse
import json
from pathlib import Path

from common import (
    QuarantineRow,
    as_bool_yn,
    as_datetime_from_text,
    as_decimal,
    as_long,
    as_string,
    as_utc_datetime,
    oracle_connection,
    reset_collections,
    strip_missing,
    target_database,
    write_quarantine,
)

UNIT = "u-01-tenancy"
WRITE_TARGETS = ("tenants", "plans", "subscriptions", "subscriptionsHist")
HIST_DT_FORMAT = "%d-%b-%y %H:%M:%S"


def tenant_document(row):
    return {
        "_id": as_string(row["ID"], "ID"),
        "name": as_string(row["NAME"], "NAME"),
        "taxExempt": as_bool_yn(row["TAX_EXEMPT_YN"], "TAX_EXEMPT_YN"),
        "statusCd": as_long(row["STATUS_CD"], "STATUS_CD"),
    }


def plan_document(row):
    return {
        "_id": as_string(row["ID"], "ID"),
        "code": as_string(row["CODE"], "CODE"),
        "tierCd": as_long(row["TIER_CD"], "TIER_CD"),
        "monthlyFee": as_decimal(row["MONTHLY_FEE"], "MONTHLY_FEE", 2),
        "includedUnits": as_long(row["INCLUDED_UNITS"], "INCLUDED_UNITS"),
        "overageRate": as_decimal(row["OVERAGE_RATE"], "OVERAGE_RATE", 6),
        "active": as_bool_yn(row["ACTIVE_YN"], "ACTIVE_YN"),
    }


def subscription_document(row):
    document = {
        "_id": as_string(row["ID"], "ID"),
        "tenantId": as_string(row["TENANT_ID"], "TENANT_ID"),
        "planId": as_string(row["PLAN_ID"], "PLAN_ID"),
        "startsOn": as_utc_datetime(row["STARTS_ON"], "STARTS_ON"),
        "endsOn": as_utc_datetime(row["ENDS_ON"], "ENDS_ON"),
        "statusCd": as_long(row["STATUS_CD"], "STATUS_CD"),
        "suspendedOn": as_utc_datetime(row["SUSPENDED_ON"], "SUSPENDED_ON"),
    }
    return strip_missing(document, {"endsOn", "suspendedOn"})


def subscription_hist_document(row):
    document = {
        "_id": as_long(row["HIST_ID"], "HIST_ID"),
        "histDt": as_datetime_from_text(row["HIST_DT"], "HIST_DT", HIST_DT_FORMAT),
        "histOp": as_string(row["HIST_OP"], "HIST_OP"),
        "id": as_string(row["ID"], "ID"),
        "tenantId": as_string(row["TENANT_ID"], "TENANT_ID"),
        "planId": as_string(row["PLAN_ID"], "PLAN_ID"),
        "startsOn": as_utc_datetime(row["STARTS_ON"], "STARTS_ON"),
        "endsOn": as_utc_datetime(row["ENDS_ON"], "ENDS_ON"),
        "statusCd": as_long(row["STATUS_CD"], "STATUS_CD"),
        "suspendedOn": as_utc_datetime(row["SUSPENDED_ON"], "SUSPENDED_ON"),
    }
    optional = set(document) - {"_id"}
    return strip_missing(document, optional)


TABLES = (
    ("TENANTS", "tenants", "SELECT id, name, tax_exempt_yn, status_cd FROM tenants ORDER BY id",
     tenant_document, ("ID",)),
    ("PLANS", "plans",
     "SELECT id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn FROM plans ORDER BY id",
     plan_document, ("ID",)),
    ("SUBSCRIPTIONS", "subscriptions",
     "SELECT id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on FROM subscriptions ORDER BY id",
     subscription_document, ("ID",)),
    ("SUBSCRIPTIONS_HIST", "subscriptionsHist",
     ("SELECT hist_id, hist_dt, hist_op, id, tenant_id, plan_id, starts_on, ends_on, "
      "status_cd, suspended_on FROM subscriptions_hist ORDER BY hist_id"),
     subscription_hist_document, ("HIST_ID",)),
)


def load(source, db, quarantine):
    reset_collections(db, WRITE_TARGETS, WRITE_TARGETS)
    counts = {}
    for table, collection, sql, convert, key_columns in TABLES:
        documents = []
        with source.cursor() as cursor:
            cursor.execute(sql)
            names = [column[0] for column in cursor.description]
            for values in cursor:
                row = dict(zip(names, values))
                try:
                    document = convert(row)
                    if document["_id"] is None:
                        raise QuarantineRow("null_key", key_columns[0], None)
                except QuarantineRow as problem:
                    quarantine.append({
                        "table": table,
                        "key": {column: str(row[column]) for column in key_columns},
                        "reason": problem.reason,
                        "column": problem.column,
                    })
                    continue
                documents.append(document)
        if documents:
            db[collection].insert_many(documents, ordered=True)
        counts[collection] = {"source_rows": len(documents) + sum(
            1 for q in quarantine if q["table"] == table), "loaded": len(documents)}
    db["subscriptions"].create_index([("tenantId", 1), ("startsOn", -1)])
    db["plans"].create_index([("code", 1)], unique=True)
    db["tenants"].create_index([("name", 1)], unique=True)
    db["subscriptionsHist"].create_index([("id", 1), ("histDt", 1)])
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", required=True)
    parser.add_argument("--target-uri-secret", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--quarantine-out", required=True, type=Path)
    args = parser.parse_args()

    quarantine = []
    db = target_database(args.target_uri_secret, args.target_db)
    with oracle_connection(args.source_dsn_secret) as source:
        counts = load(source, db, quarantine)
    by_reason = write_quarantine(args.quarantine_out / "quarantine.json", quarantine)
    summary = {"unit": UNIT, "collections": counts, "quarantined": len(quarantine),
               "quarantine_by_reason": by_reason}
    (args.quarantine_out / "load.summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
