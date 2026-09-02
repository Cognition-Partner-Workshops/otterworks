import json, os, sys
from pymongo import MongoClient
db=MongoClient(os.environ["MONGODB_ATLAS_URI"])["ow_tp_mongodb_205236"]
coll=sys.argv[1]
out={"collection":coll,"invoices":0,"lines":0,"bad":[]}
for d in db[coll].find({}, sort=[("_id",1)]):
    out["invoices"]+=1
    for i,l in enumerate(d.get("lines") or []):
        out["lines"]+=1
        if l.get("invoice_id") is None or l["invoice_id"]!=d["_id"] or l["invoice_id"]!=d.get("id"):
            out["bad"].append({"invoice":d["_id"],"idx":i,"invoice_id":l.get("invoice_id")})
out["by_invoice"]={d["_id"]:len(d.get("lines") or []) for d in db[coll].find({}, sort=[("_id",1)])}
out["ok"]=not out["bad"]
print(json.dumps(out,indent=1,default=str))
