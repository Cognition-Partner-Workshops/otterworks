"""Wave-1 independent adversarial probes for U4 (DynamoDB otterworks-file-metadata ns=demo -> Mongo files)."""
import os, json, collections
from decimal import Decimal
from datetime import datetime, timezone
import boto3, pymongo

c = pymongo.MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = c["ow_tp_mongodb_205236"]; qdb = c["ow_tp_mongodb_205236_quarantine"]
sess = boto3.Session(aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")
ddb = sess.resource("dynamodb", endpoint_url="http://localhost:4566").Table("otterworks-file-metadata")
s3 = sess.client("s3", endpoint_url="http://localhost:4566")
out = {}
def rec(name, ok, detail): out[name] = {"ok": bool(ok), "detail": detail}; print(("PASS " if ok else "FAIL ") + name, "|", detail)

items = []; kw = {"ConsistentRead": True}
while True:
    r = ddb.scan(**kw); items += r["Items"]
    if "LastEvaluatedKey" not in r: break
    kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
src = {it["id"]: it for it in items if it.get("ns") == "demo"}
rec("U4.source_scan", len(items) == 10000 and len(src) == 10000, {"items_total": len(items), "ns=demo": len(src), "other_ns": collections.Counter(it.get("ns") for it in items if it.get("ns") != "demo")})
tgt = {d["_id"]: d for d in db.files.find()}
rec("U4.keyset_equal", set(src) == set(tgt), {"src_only": len(set(src) - set(tgt)), "tgt_only": len(set(tgt) - set(src))})

# 1. attribute presence / null distribution (Dynamo has no NULL; attribute may be absent or NULL-typed)
attrs = ["name","mime_type","size_bytes","s3_key","owner_id","folder_id","is_trashed","version","created_at","updated_at","ns"]
pres = {a: sum(1 for it in src.values() if a in it and it[a] is not None) for a in attrs}
tpres = {a: db.files.count_documents({("source_ns" if a == "ns" else a): {"$exists": True, "$ne": None}}) for a in attrs}
tnull = {a: db.files.count_documents({("source_ns" if a == "ns" else a): {"$type": "null"}}) for a in attrs}
tmiss = {a: db.files.count_documents({("source_ns" if a == "ns" else a): {"$exists": False}}) for a in attrs}
rec("U4.null_dist", pres == tpres, {"src_present": pres, "tgt_present": tpres, "tgt_null": {k: v for k, v in tnull.items() if v}, "tgt_missing": {k: v for k, v in tmiss.items() if v}})
rec("U4.explicit_null_policy(D2)", not any(tmiss.values()), {k: v for k, v in tmiss.items() if v})
src_attr_sets = collections.Counter(tuple(sorted(it.keys())) for it in src.values())
rec("U4.source_attribute_shape", len(src_attr_sets) == 1, {str(k): v for k, v in src_attr_sets.items()})

# 2. fieldset / ns / types
ks = collections.Counter(k for d in tgt.values() for k in d)
exp = {"_id","name","mime_type","size_bytes","s3_key","owner_id","folder_id","is_trashed","version","created_at","updated_at","source_ns","ns","orphaned_metadata"}
rec("U4.fieldset", set(ks) == exp, {"extra": sorted(set(ks) - exp), "missing": sorted(exp - set(ks)), "counts": dict(ks)})
rec("U4.ns_marker", db.files.count_documents({"ns": {"$ne": "mongo_205236"}}) == 0 and db.files.count_documents({"source_ns": {"$ne": "demo"}}) == 0, "")
def types(f): return {d["_id"]: d["n"] for d in db.files.aggregate([{"$group": {"_id": {"$type": f"${f}"}, "n": {"$sum": 1}}}])}
exp_t = {"_id": {"string"}, "name": {"string"}, "mime_type": {"string"}, "size_bytes": {"long"}, "s3_key": {"string"}, "owner_id": {"string"}, "folder_id": {"string", "null"}, "is_trashed": {"bool"}, "version": {"int"}, "created_at": {"date"}, "updated_at": {"date"}, "source_ns": {"string"}, "orphaned_metadata": {"bool"}}
bad = {f: types(f) for f, a in exp_t.items() if set(types(f)) - a}
rec("U4.bson_types(spec: size_bytes long, version int)", not bad, bad or {f: types(f) for f in ("size_bytes", "version")})

# 3. duplicates
for a in ("s3_key", "name"):
    sd = sum(1 for k, v in collections.Counter(it.get(a) for it in src.values()).items() if v > 1)
    td = len(list(db.files.aggregate([{"$group": {"_id": f"${a}", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}])))
    rec(f"U4.dup.{a}", sd == td, {"src_dup_values": sd, "tgt_dup_values": td})

# 4. full value diff, independently (not via harness): every item, every attribute
def norm_src(a, v):
    if a in ("size_bytes", "version"): return int(v)
    if a in ("created_at", "updated_at"):
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00")); return dt.astimezone(timezone.utc).replace(microsecond=(dt.microsecond // 1000) * 1000)
    if a == "is_trashed": return bool(v)
    return v
def norm_tgt(v):
    if isinstance(v, datetime): return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
    return v
diffs = []
for k, it in src.items():
    d = tgt.get(k)
    if d is None: continue
    for a in attrs:
        ta = "source_ns" if a == "ns" else a
        sv = norm_src(a, it.get(a)) if it.get(a) is not None else None
        tv = norm_tgt(d.get(ta))
        if sv != tv: diffs.append((k, a, str(sv)[:40], str(tv)[:40]))
rec("U4.full_value_diff_independent", not diffs, {"n_diffs": len(diffs), "sample": diffs[:5]})
# sub-second precision check: any source timestamps with fractional seconds? (truncate_ms rule)
frac = sum(1 for it in src.values() for a in ("created_at", "updated_at") if "." in str(it[a]))
rec("U4.timestamp_fraction_info", True, {"src_timestamps_with_fraction": frac, "note": "rule datetime_utc_truncate_ms is a no-op when 0"})

# 5. min/max boundary docs
for a in ("size_bytes", "version", "created_at", "updated_at", "name"):
    vals = sorted(src.values(), key=lambda it: norm_src(a, it[a]))
    for it in vals[:3] + vals[-3:]:
        d = tgt[it["id"]]
        assert norm_tgt(d[a]) == norm_src(a, it[a]), (a, it["id"])
rec("U4.boundary_docs", True, {"size_bytes": [int(vals[0]["size_bytes"]) if a == "name" else None], "min_size": min(int(i["size_bytes"]) for i in src.values()), "max_size": max(int(i["size_bytes"]) for i in src.values())})
# size_bytes sum exactness (long) and > int32 values present
big = sum(1 for it in src.values() if int(it["size_bytes"]) > 2**31 - 1)
tsum = next(db.files.aggregate([{"$group": {"_id": None, "s": {"$sum": "$size_bytes"}}}]))["s"]
rec("U4.size_bytes_sum_exact", tsum == sum(int(it["size_bytes"]) for it in src.values()), {"sum": int(tsum), "values_gt_int32": big})

# 6. derived orphaned_metadata (ungraded in gate) vs S3 truth and vs seed rule (s3_key prefix demo/missing/)
marked = {d["_id"] for d in db.files.find({"orphaned_metadata": True}, {"_id": 1})}
by_prefix = {k for k, it in src.items() if it["s3_key"].startswith("demo/missing/")}
buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
s3_missing = None; bucket_used = None
for b in buckets:
    try:
        keys = set()
        pag = s3.get_paginator("list_objects_v2")
        for page in pag.paginate(Bucket=b, Prefix="demo/"):
            keys |= {o["Key"] for o in page.get("Contents", [])}
        if keys:
            bucket_used = b; s3_missing = {k for k, it in src.items() if it["s3_key"] not in keys}
            break
    except Exception as e:
        pass
rec("U4.orphaned_metadata_vs_seed_rule", marked == by_prefix and len(marked) == 40, {"marked": len(marked), "by_prefix": len(by_prefix), "expected": 40, "symdiff": len(marked ^ by_prefix)})
rec("U4.orphaned_metadata_vs_s3(informational)", s3_missing is None or marked == s3_missing, {"buckets": buckets, "bucket_with_demo_prefix": bucket_used, "s3_missing": None if s3_missing is None else len(s3_missing), "note": "no S3 objects for file keys in LocalStack -> S3 truth unavailable; seed rule used" if s3_missing is None else ""})
rec("U4.no_quarantine_expected", not [c for c in qdb.list_collection_names() if "file" in c or "U4" in c], qdb.list_collection_names())

# 7. indexes
rec("U4.indexes", {tuple(i["key"].items()) for i in db.files.list_indexes()} >= {(("owner_id", 1), ("is_trashed", 1)), (("folder_id", 1),)}, [i["name"] for i in db.files.list_indexes()])

# 8. app-level replay (file-service metadata.rs list_files / list_trashed)
owners = collections.Counter(it["owner_id"] for it in src.values()).most_common()
folders = collections.Counter(it["folder_id"] for it in src.values()).most_common()
fails = []; n = 0
def src_list(folder=None, owner=None, include_trashed=False):
    return sorted(k for k, it in src.items() if (folder is None or it["folder_id"] == folder) and (owner is None or it["owner_id"] == owner) and (include_trashed or it["is_trashed"] is False))
def tgt_list(folder=None, owner=None, include_trashed=False):
    q = {}
    if folder: q["folder_id"] = folder
    if owner: q["owner_id"] = owner
    if not include_trashed: q["is_trashed"] = False
    return sorted(d["_id"] for d in db.files.find(q, {"_id": 1}))
for owner in (owners[0][0], owners[len(owners) // 2][0], owners[-1][0], None):
    for folder in (folders[0][0], folders[-1][0], None):
        for inc in (False, True):
            n += 1
            if src_list(folder, owner, inc) != tgt_list(folder, owner, inc): fails.append((owner, folder, inc))
rec("U4.replay.list_files", not fails, {"ops": n, "fails": fails[:3]})
fails = []; n = 0
for owner in (owners[0][0], owners[len(owners) // 2][0], owners[-1][0], None):
    n += 1
    s = [k for k, it in sorted(src.items(), key=lambda kv: (norm_src("updated_at", kv[1]["updated_at"]), kv[0]), reverse=True) if it["is_trashed"] is True and (owner is None or it["owner_id"] == owner)]
    q = {"is_trashed": True}; q.update({"owner_id": owner} if owner else {})
    t = [d["_id"] for d in db.files.find(q, {"_id": 1}).sort([("updated_at", -1), ("_id", -1)])]
    if s != t: fails.append(owner)
rec("U4.replay.list_trashed(sorted updated_at desc)", not fails, {"ops": n, "fails": fails})
gets = 0
for k in list(src)[::200]:
    gets += 1
    assert db.files.find_one({"_id": k}) is not None
rec("U4.replay.get_file", True, {"ops": gets})
# storage_cleanup_daily.py: set of s3_keys referenced
rec("U4.replay.storage_cleanup_s3key_set", {it["s3_key"] for it in src.values()} == {d["s3_key"] for d in tgt.values()}, "")
# distribution
for f in ("is_trashed", "mime_type", "version"):
    s = collections.Counter(str(norm_src(f, it[f])).lower() for it in src.values())
    t = {str(d["_id"]).lower(): d["n"] for d in db.files.aggregate([{"$group": {"_id": f"${f}", "n": {"$sum": 1}}}])}
    rec(f"U4.dist.{f}", dict(s) == t, dict(s) if dict(s) == t else {"src": dict(s), "tgt": t})

json.dump(out, open("/tmp/wr/u4/probes.json", "w"), indent=1, default=str)
print("\nSUMMARY U4:", sum(1 for v in out.values() if v["ok"]), "/", len(out), "probes ok")

# 9. head-3420f475 loader (stage into files__u4_staging + rename dropTarget): residue + shape checks
names = db.list_collection_names()
rec("U4.no_staging_residue", "files__u4_staging" not in names, names)
rec("U4.only_U4_collection_touched(other collection counts unchanged)", {n: db[n].estimated_document_count() for n in ("codes","tenants","plans","documents","document_snapshots")} == {"codes":32,"tenants":69,"plans":3,"documents":2000,"document_snapshots":384}, {n: db[n].estimated_document_count() for n in names})
rec("U4.index_names_after_rename", sorted(i["name"] for i in db.files.list_indexes()) == ["_id_", "folder_id_1", "owner_id_1_is_trashed_1"], sorted(i["name"] for i in db.files.list_indexes()))
# ns partition: strata drawn from mapped partition (loader/adapters use root_where ns='demo'); no non-demo leakage
rec("U4.no_non_demo_leak", db.files.count_documents({"source_ns": {"$ne": "demo"}}) == 0, "")
# orphaned_metadata SET vs source rule, duplicates of _id impossible but check s3_key->_id 1:1
rec("U4.s3_key_to_id_bijection", db.files.distinct("s3_key").__len__() == 10000, "")
json.dump(out, open("/tmp/wr/u4/probes.json", "w"), indent=1, default=str)
print("\nSUMMARY U4 (ext):", sum(1 for v in out.values() if v["ok"]), "/", len(out), "probes ok")
