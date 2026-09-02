import os, pymongo, json, hashlib, bson
from bson.json_util import dumps, CANONICAL_JSON_OPTIONS
c=pymongo.MongoClient(os.environ["MONGODB_ATLAS_URI"], serverSelectionTimeoutMS=15000)
db=c["ow_tp_mongodb_205236"]; q=c["ow_tp_mongodb_205236_quarantine"]
names=sorted(db.list_collection_names())
out={"collections":{n:db[n].count_documents({}) for n in names}}
def sumlen(col,f): return next(db[col].aggregate([{"$group":{"_id":None,"n":{"$sum":{"$size":{"$ifNull":["$"+f,[]]}}}}}]),{}).get("n")
for pre in ["","replay_u8_","replay_u9_"]:
    if pre+"rating_periods" in names: out[pre+"sum_results_len"]=sumlen(pre+"rating_periods","results")
    if pre+"billing_invoices" in names: out[pre+"sum_lines_len"]=sumlen(pre+"billing_invoices","lines")
    if pre+"counters" in names: out[pre+"counters"]=list(db[pre+"counters"].find({}))
    if pre+"billing_audit_log" in names: out[pre+"audit_ids"]=[d["_id"] for d in db[pre+"billing_audit_log"].find({},{"_id":1}).sort("_id",1)]
out["staging_residue"]=[n for n in names if "__staging" in n]
out["quarantine_all"]={n:q[n].count_documents({}) for n in sorted(q.list_collection_names())}
# canonical fingerprints of replay clones vs golden
def fp(col, drop_id=False):
    h=hashlib.sha256()
    for d in db[col].find({},sort=[("_id",1)]):
        if drop_id: d.pop("_id",None)
        h.update(dumps(d,json_options=CANONICAL_JSON_OPTIONS,sort_keys=True).encode())
    return h.hexdigest()
out["clone_vs_golden"]={}
for pre in ["replay_u8_","replay_u9_"]:
    for n in names:
        if n.startswith(pre):
            g=n[len(pre):]
            if g in names and g!="counters":
                di = g=="codes"
                out["clone_vs_golden"][n]={"clone":fp(n,di)[:16],"golden":fp(g,di)[:16]}
                out["clone_vs_golden"][n]["equal"]=out["clone_vs_golden"][n]["clone"]==out["clone_vs_golden"][n]["golden"]
print(json.dumps(out,default=str,indent=1))
