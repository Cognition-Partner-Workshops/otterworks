"""Batch w1-b01 loader: identity lift of users and folders into mmp_rt_billing_n.

--mode fixture reads mmp_rt_billing_n.fx_src_<collection> (MONGODB_MMP_RT_TARGET_N_URI).
--mode live    reads mmp_rt_src.<collection>              (MONGODB_MMP_RT_SOURCE_URI, read-only).
Writes only mmp_rt_billing_n.users and mmp_rt_billing_n.folders (drop + recreate every run).
"""
import argparse
import json
import os
import sys

from bson.raw_bson import RawBSONDocument
from pymongo import MongoClient

targetDb = "mmp_rt_billing_n"
sourceDb = "mmp_rt_src"
batchSize = 1000
units = ["users", "folders"]
indexPlan = {
    "users": [{"key": [("email", 1)], "name": "email_1"}],
    "folders": [],
}


def connect(secretName):
    uri = os.environ.get(secretName)
    if not uri:
        sys.exit(f"missing secret env var {secretName}")
    return MongoClient(uri, document_class=RawBSONDocument, appname="mmp-rt-w1-b01-loader")


def describeIndexes(collection):
    return [
        {k: v for k, v in dict(ix).items() if k not in ("v", "ns")}
        for ix in collection.list_indexes()
    ]


def insertBatch(targetColl, batch):
    result = targetColl.insert_many(batch, ordered=False)
    if not result.acknowledged:
        sys.exit(f"unacknowledged insert into {targetColl.full_name}")
    return len(batch)


def loadUnit(sourceColl, targetColl, name):
    targetColl.drop()
    targetColl.database.create_collection(name)
    batch = []
    inserted = 0
    for doc in sourceColl.find({}, batch_size=batchSize).sort("_id", 1):
        batch.append(doc)
        if len(batch) >= batchSize:
            inserted += insertBatch(targetColl, batch)
            batch = []
    if batch:
        inserted += insertBatch(targetColl, batch)
    for ix in indexPlan[name]:
        targetColl.create_index(ix["key"], name=ix["name"])
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixture", "live"], required=True)
    args = parser.parse_args()

    targetClient = connect("MONGODB_MMP_RT_TARGET_N_URI")
    target = targetClient[targetDb]
    if args.mode == "fixture":
        sourceClient = targetClient
        source = target
        sourceName = lambda c: f"fx_src_{c}"
    else:
        sourceClient = connect("MONGODB_MMP_RT_SOURCE_URI")
        source = sourceClient[sourceDb]
        sourceName = lambda c: c

    report = {"mode": args.mode, "units": {}}
    for name in units:
        srcColl = source[sourceName(name)]
        tgtColl = target[name]
        sourceCount = srcColl.count_documents({})
        inserted = loadUnit(srcColl, tgtColl, name)
        report["units"][name] = {
            "source": f"{srcColl.database.name}.{srcColl.name}",
            "target": f"{targetDb}.{name}",
            "sourceCount": sourceCount,
            "inserted": inserted,
            "targetCount": tgtColl.count_documents({}),
            "sourceIndexes": describeIndexes(srcColl),
            "targetIndexes": describeIndexes(tgtColl),
        }
    print(json.dumps(report, indent=1, default=str))
    ok = all(
        u["sourceCount"] == u["inserted"] == u["targetCount"] for u in report["units"].values()
    )
    sourceClient.close()
    if sourceClient is not targetClient:
        targetClient.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
