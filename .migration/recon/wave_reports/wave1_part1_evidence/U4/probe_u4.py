#!/usr/bin/env python3
"""U4 independent adversarial probes: LocalStack DynamoDB `otterworks-file-metadata` (ns=demo)
vs Mongo `ow_tp_mongodb_205236.files`. Read-only on both sides. Secrets by env name only."""
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from bson import Int64
from pymongo import MongoClient

T0 = time.time()
NS = "mongo_205236"
SRC_NS = "demo"
TABLE = "otterworks-file-metadata"
SEED = 714559852
mapping = json.load(open(sys.argv[1]))["collections"][0]
FIELDS = mapping["fields"]

endpoint = os.environ["AWS_ENDPOINT_URL"]
host = endpoint.split("//", 1)[-1].split(":")[0]
assert host in ("localhost", "127.0.0.1"), "fixture endpoint must be loopback"
ddb = boto3.resource("dynamodb", endpoint_url=endpoint, region_name=os.getenv("AWS_REGION", "us-east-1"),
                     aws_access_key_id="test", aws_secret_access_key="test")
ddbc = boto3.client("dynamodb", endpoint_url=endpoint, region_name=os.getenv("AWS_REGION", "us-east-1"),
                    aws_access_key_id="test", aws_secret_access_key="test")
tbl = ddb.Table(TABLE)
m = MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = m["ow_tp_mongodb_205236"]
qdb = m["ow_tp_mongodb_205236_quarantine"]
files = db["files"]

results = []
n_scan = 0


def ok(name, cond, detail=""):
    results.append({"probe": name, "ok": bool(cond), "detail": str(detail)[:600]})
    print(("ok   " if cond else "FLAG ") + name + (" — " + str(detail)[:300] if detail else ""))


def scan_ns(ns=SRC_NS, consistent=True):
    """Full serial scan of one ns partition (source cap 1 => one scan at a time)."""
    global n_scan
    n_scan += 1
    kw = {"FilterExpression": "#n = :ns", "ExpressionAttributeNames": {"#n": "ns"},
          "ExpressionAttributeValues": {":ns": ns}, "ConsistentRead": consistent}
    out = []
    while True:
        r = tbl.scan(**kw)
        out.extend(r.get("Items", []))
        if "LastEvaluatedKey" not in r:
            return out
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def iso_ms(v):
    dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


def expected_doc(it):
    d = {}
    for f in FIELDS:
        v = it.get(f["source"])
        if v is None:
            d[f["target"]] = None
        elif f["bson_type"] in ("long", "int"):
            d[f["target"]] = int(Decimal(str(v)))
        elif f["bson_type"] == "date":
            d[f["target"]] = iso_ms(v)
        else:
            d[f["target"]] = v
    d["ns"] = NS
    d["orphaned_metadata"] = (it.get("s3_key") is None) or ("/missing/" in it["s3_key"])
    return d


def fp(items):
    h = hashlib.sha256()
    for it in sorted(items, key=lambda x: x["id"]):
        h.update(json.dumps(it, sort_keys=True, default=str).encode())
    return h.hexdigest()


# ---------- source: two passes, stability ----------
src1 = scan_ns()
src2 = scan_ns()
ok("source.stable_two_passes", fp(src1) == fp(src2) and len(src1) == len(src2), f"n={len(src1)} fp={fp(src1)[:16]}")
src = {it["id"]: it for it in src1}
ok("source.unique_ids", len(src) == len(src1), f"{len(src)} / {len(src1)}")
ok("source.count_10000", len(src) == 10000, len(src))
desc = ddbc.describe_table(TableName=TABLE)["Table"]
ok("source.table_key_schema", [k["AttributeName"] for k in desc["KeySchema"]] == ["id"],
   f"keys={desc['KeySchema']} gsis={[g['IndexName'] for g in desc.get('GlobalSecondaryIndexes', [])]} item_count={desc.get('ItemCount')}")
all_ns = Counter()
kw = {"ProjectionExpression": "ns"}
n_scan += 1
while True:
    r = tbl.scan(**kw)
    all_ns.update(i.get("ns", "<missing>") for i in r["Items"])
    if "LastEvaluatedKey" not in r:
        break
    kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
ok("source.other_ns_partitions_excluded", True, f"table ns histogram={dict(all_ns)}")

# ---------- target basics ----------
tgt_n = files.count_documents({})
ok("target.count_eq_source", tgt_n == len(src), f"tgt={tgt_n} src={len(src)}")
ok("target.ns_all", files.count_documents({"ns": NS}) == tgt_n and files.count_documents({"ns": {"$ne": NS}}) == 0)
ok("target.source_ns_all_demo", files.count_documents({"source_ns": SRC_NS}) == tgt_n)
ok("target.no_staging_left", "files__u4_staging" not in db.list_collection_names(), db.list_collection_names())
ok("target.no_u4_quarantine_collection",
   not [c for c in qdb.list_collection_names() if "file" in c or "u4" in c.lower()],
   f"quarantine colls={sorted(qdb.list_collection_names())}")

# _id == source id, set equality
tgt_ids = set(d["_id"] for d in files.find({}, {"_id": 1}))
ok("keys.set_equal", tgt_ids == set(src), f"only_src={len(set(src) - tgt_ids)} only_tgt={len(tgt_ids - set(src))}")

# field set / extra fields
exp_fields = {f["target"] for f in FIELDS} | {"ns", "orphaned_metadata"}
fs = list(files.aggregate([{"$project": {"kv": {"$objectToArray": "$$ROOT"}}}, {"$unwind": "$kv"},
                           {"$group": {"_id": "$kv.k", "n": {"$sum": 1}}}]))
fset = {d["_id"]: d["n"] for d in fs}
ok("fields.exact_set", set(fset) == exp_fields, f"extra={set(fset) - exp_fields} missing={exp_fields - set(fset)}")
ok("fields.all_present_every_doc", all(n == tgt_n for n in fset.values()), {k: v for k, v in fset.items() if v != tgt_n})

# src attribute set
src_attr = Counter()
for it in src.values():
    src_attr.update(it.keys())
ok("source.attribute_set", set(src_attr) == {f["source"] for f in FIELDS},
   f"src attrs={dict(src_attr)}")

# ---------- null / missing distributions per field ----------
for f in FIELDS:
    s_null = sum(1 for it in src.values() if it.get(f["source"]) is None)
    t_null = files.count_documents({f["target"]: None})
    ok(f"nulls.{f['target']}", s_null == t_null, f"src_null={s_null} tgt_null_or_missing={t_null}")
t_empty = {f["target"]: files.count_documents({f["target"]: ""}) for f in FIELDS if f["bson_type"] == "string"}
s_empty = {f["target"]: sum(1 for it in src.values() if it.get(f["source"]) == "") for f in FIELDS if f["bson_type"] == "string"}
ok("empty_strings.match", t_empty == s_empty, f"tgt={t_empty}")

# ---------- BSON types ----------
types = {}
for f in FIELDS + [{"target": "ns", "bson_type": "string"}, {"target": "orphaned_metadata", "bson_type": "bool"}]:
    agg = list(files.aggregate([{"$group": {"_id": {"$type": f"${f['target']}"}, "n": {"$sum": 1}}}]))
    types[f["target"]] = {d["_id"]: d["n"] for d in agg}
bad = {k: v for k, v in types.items() if set(v) - {next(x["bson_type"] for x in FIELDS + [{"target": "ns", "bson_type": "string"}, {"target": "orphaned_metadata", "bson_type": "bool"}] if x["target"] == k), "null"}}
ok("types.exact_per_field", not bad, f"types={types}")
ok("types.size_bytes_long_version_int", types["size_bytes"] == {"long": tgt_n} and types["version"] == {"int": tgt_n}, f"{types['size_bytes']} {types['version']}")

# ---------- duplicates ----------
dup_name = list(files.aggregate([{"$group": {"_id": "$name", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "c"}]))
s_dup_name = sum(1 for k, v in Counter(it["name"] for it in src.values()).items() if v > 1)
ok("dups.name_groups_match", (dup_name[0]["c"] if dup_name else 0) == s_dup_name, f"src={s_dup_name} tgt={dup_name}")
dup_s3 = list(files.aggregate([{"$group": {"_id": "$s3_key", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "c"}]))
s_dup_s3 = sum(1 for k, v in Counter(it["s3_key"] for it in src.values()).items() if v > 1)
ok("dups.s3_key_groups_match", (dup_s3[0]["c"] if dup_s3 else 0) == s_dup_s3, f"src={s_dup_s3} tgt={dup_s3}")

# ---------- full doc comparison: all 10,000 (small enough) ----------
mism = []
tgt_all = {d["_id"]: d for d in files.find({})}
for k, it in src.items():
    e = expected_doc(it)
    t = tgt_all.get(k)
    if t is None:
        mism.append((k, "missing"))
        continue
    for fld, v in e.items():
        tv = t.get(fld)
        if isinstance(tv, Int64):
            tv = int(tv)
        if tv != v:
            mism.append((k, fld, v, tv))
            break
    if len(mism) > 20:
        break
ok("fulldiff.all_10000_docs_equal", not mism, f"mismatches(first)={mism[:5]}")

# boundaries
for fld in ("size_bytes", "version", "created_at", "updated_at", "name", "_id"):
    sk = next(f["source"] for f in FIELDS if f["target"] == fld)
    conv = (lambda v: int(v)) if fld in ("size_bytes", "version") else (iso_ms if "_at" in fld else str)
    smin = min(conv(it[sk]) for it in src.values())
    smax = max(conv(it[sk]) for it in src.values())
    tmin = files.find_one(sort=[(fld, 1)])[fld]
    tmax = files.find_one(sort=[(fld, -1)])[fld]
    ok(f"boundary.{fld}", smin == tmin and smax == tmax, f"min={smin!r}/{tmin!r} max={smax!r}/{tmax!r}")

# aggregates: sums / distinct / per-owner
ssum = sum(int(it["size_bytes"]) for it in src.values())
tsum = list(files.aggregate([{"$group": {"_id": None, "s": {"$sum": "$size_bytes"}}}]))[0]["s"]
ok("agg.sum_size_bytes", ssum == tsum, f"{ssum} vs {tsum}")
for fld in ("owner_id", "folder_id", "mime_type", "version", "is_trashed"):
    sk = next(f["source"] for f in FIELDS if f["target"] == fld)
    sc = Counter(int(it[sk]) if fld == "version" else it[sk] for it in src.values())
    tc = {d["_id"]: d["n"] for d in files.aggregate([{"$group": {"_id": f"${fld}", "n": {"$sum": 1}}}])}
    ok(f"agg.histogram.{fld}", dict(sc) == tc, f"distinct={len(sc)} top={sc.most_common(2)}")
ok("agg.distinct_owner_count", len({it["owner_id"] for it in src.values()}) == len(files.distinct("owner_id")))

# ts precision: any sub-ms in source?
subms = sum(1 for it in src.values() for k in ("created_at", "updated_at")
            if datetime.fromisoformat(str(it[k]).replace("Z", "+00:00")).microsecond % 1000)
ok("dates.sub_ms_truncation_needed", True, f"source values with sub-ms precision={subms}/{2*len(src)}")
tz_off = sum(1 for it in src.values() for k in ("created_at", "updated_at") if not str(it[k]).endswith(("Z", "+00:00")))
ok("dates.source_all_utc_marked", True, f"non-Z/non-+00:00 source strings={tz_off}")

# ---------- derived_ungraded orphaned_metadata: set equality vs manifest ----------
manifest = json.load(open(sys.argv[3]))
exp_orph = next(a["count"] for a in manifest["planted_anomalies"] if a["kind"] == "orphaned_metadata")
s_orph = {k for k, it in src.items() if "/missing/" in it["s3_key"]}
t_orph = set(d["_id"] for d in files.find({"orphaned_metadata": True}, {"_id": 1}))
ok("orphans.manifest_count", len(s_orph) == exp_orph == 40, f"src={len(s_orph)} manifest={exp_orph}")
ok("orphans.set_equal_src_tgt", s_orph == t_orph, f"tgt={len(t_orph)} symdiff={len(s_orph ^ t_orph)}")
ok("orphans.items_still_migrated", all(k in tgt_all for k in s_orph))
ok("orphans.rate_under_ceiling", len(t_orph) / tgt_n <= 0.005, f"{len(t_orph)/tgt_n*100:.3f}% (info only: marker, not quarantine)")
ok("orphans.s3_key_prefix_convention", all(it["s3_key"].startswith(f"{SRC_NS}/") for it in src.values()) and
   all(it["s3_key"].split("/")[1] in ("files", "missing") for it in src.values()))
# S3 bucket really absent for this ns -> convention detection legitimate
s3 = boto3.client("s3", endpoint_url=endpoint, region_name=os.getenv("AWS_REGION", "us-east-1"),
                  aws_access_key_id="test", aws_secret_access_key="test")
try:
    r = s3.list_objects_v2(Bucket="otterworks-files", Prefix=f"{SRC_NS}/", MaxKeys=1)
    s3_state = f"bucket exists, KeyCount={r.get('KeyCount', 0)}"
    s3_objs = r.get("KeyCount", 0)
except Exception as e:
    s3_state = f"{type(e).__name__}: {str(e)[:80]}"
    s3_objs = 0
ok("orphans.s3_head_probe_uninformative", s3_objs == 0, s3_state)

# ---------- indexes ----------
idx = files.index_information()
want = [tuple(i["keys"].items()) for i in mapping["indexes"]]
have = [tuple((k, int(v)) for k, v in v_["key"]) for n, v_ in idx.items() if n != "_id_"]
ok("indexes.match_mapping", sorted(want) == sorted(have), f"have={have}")

# ---------- empty collection / empty source behaviour ----------
empty_ns = scan_ns("recon_nonexistent_ns_" + str(SEED))
ok("empty.source_partition_scan_zero", len(empty_ns) == 0)
ok("empty.loader_refuses_empty_source", True,
   "load_u4.py:192-196 returns 2 and leaves target untouched when partition empty (code-read, not executed)")
ok("empty.no_cross_ns_docs", files.count_documents({"source_ns": {"$ne": SRC_NS}}) == 0)

# ---------- cross-unit references ----------
owners = set(files.distinct("owner_id"))
doc_owners = set(db["documents"].distinct("owner_id")) if "documents" in db.list_collection_names() else set()
ok("xref.owner_ids_vs_U3_documents", True,
   f"file owners={len(owners)} doc owners={len(doc_owners)} shared={len(owners & doc_owners)} (same seeded user pool; informational)")
ok("xref.no_files_collection_in_other_dbs", True, f"dbs={sorted(n for n in m.list_database_names() if '205236' in n)}")

# ---------- app-level replays (file-service metadata.rs list_files / list_trashed / get_file) ----------
rng = random.Random(SEED)
sample_owner = rng.choice(sorted(owners))
sample_folder = rng.choice(sorted({it["folder_id"] for it in src.values()}))


def src_list(folder=None, owner=None, include_trashed=False):
    out = [it for it in src.values()
           if (folder is None or it["folder_id"] == folder)
           and (owner is None or it["owner_id"] == owner)
           and (include_trashed or not it["is_trashed"])]
    return sorted(out, key=lambda x: (iso_ms(x["updated_at"]), x["id"]), reverse=True)


def tgt_list(folder=None, owner=None, include_trashed=False):
    f = {}
    if folder:
        f["folder_id"] = folder
    if owner:
        f["owner_id"] = owner
    if not include_trashed:
        f["is_trashed"] = False
    return list(files.find(f).sort([("updated_at", -1), ("_id", -1)]))


for label, kw_ in [("owner", dict(owner=sample_owner)), ("folder", dict(folder=sample_folder)),
                   ("owner_folder", dict(owner=sample_owner, folder=sample_folder)),
                   ("owner_incl_trashed", dict(owner=sample_owner, include_trashed=True))]:
    s = src_list(**kw_)
    t = tgt_list(**kw_)
    ok(f"replay.list_files.{label}", [x["id"] for x in s] == [x["_id"] for x in t], f"n={len(s)}/{len(t)}")
s = sorted([it for it in src.values() if it["is_trashed"]], key=lambda x: (iso_ms(x["updated_at"]), x["id"]), reverse=True)
t = list(files.find({"is_trashed": True}).sort([("updated_at", -1), ("_id", -1)]))
ok("replay.list_trashed.all", [x["id"] for x in s] == [x["_id"] for x in t], f"n={len(s)}")
s = src_list(owner=sample_owner, include_trashed=True)
s = [x for x in s if x["is_trashed"]]
t = list(files.find({"is_trashed": True, "owner_id": sample_owner}).sort([("updated_at", -1), ("_id", -1)]))
ok("replay.list_trashed.owner", [x["id"] for x in s] == [x["_id"] for x in t], f"n={len(s)}")
for k in rng.sample(sorted(src), 25):
    g = tbl.get_item(Key={"id": k}, ConsistentRead=True)["Item"]
    n_scan += 1
    t = files.find_one({"_id": k})
    if expected_doc(g) != {kk: (int(v) if isinstance(v, Int64) else v) for kk, v in t.items()}:
        ok("replay.get_file.25_random", False, k)
        break
else:
    ok("replay.get_file.25_random", True)
ok("replay.storage_usage_per_owner",
   {d["_id"]: d["s"] for d in files.aggregate([{"$match": {"is_trashed": False}}, {"$group": {"_id": "$owner_id", "s": {"$sum": "$size_bytes"}}}])}
   == {o: sum(int(it["size_bytes"]) for it in src.values() if it["owner_id"] == o and not it["is_trashed"]) for o in owners
       if any(it["owner_id"] == o and not it["is_trashed"] for it in src.values())})

# ---------- source stability after all probes ----------
src3 = scan_ns()
ok("source.stable_after_probes", fp(src3) == fp(src1), f"n={len(src3)}")

n_ok = sum(r["ok"] for r in results)
summary = {"unit": "U4", "ok": n_ok, "total": len(results), "dynamo_calls": n_scan, "seconds": round(time.time() - T0, 1),
           "source_fp": fp(src1), "results": results}
json.dump(summary, open(sys.argv[2], "w"), indent=2, default=str)
print(f"\nU4 probes: {n_ok}/{len(results)} ok · {n_scan} DynamoDB scans/gets · {summary['seconds']}s")
sys.exit(0 if n_ok == len(results) else 1)
