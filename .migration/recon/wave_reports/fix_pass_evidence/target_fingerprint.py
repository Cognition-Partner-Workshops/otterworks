import json, os, sys, hashlib, bson
from pymongo import MongoClient
c=MongoClient(os.environ["MONGODB_ATLAS_URI"])
out={}
for dbn in ["ow_tp_mongodb_205236","ow_tp_mongodb_205236_quarantine"]:
    db=c[dbn]
    for name in sorted(db.list_collection_names()):
        if dbn.endswith("quarantine") or not name.startswith("replay_"):
            h=hashlib.sha256(); n=0
            for d in db[name].find({}, sort=[("_id",1)]):
                h.update(bson.encode(d) if dbn=="ow_tp_mongodb_205236" else bson.encode({k:v for k,v in d.items() if k!="_id"})); n+=1
            out[f"{dbn}.{name}"]={"n":n,"sha":h.hexdigest()}
        else:
            out[f"{dbn}.{name}"]={"n":db[name].estimated_document_count()}
out["counters_docs"]=[{k:(str(v) if k!="_id" else v) for k,v in d.items()} for d in c["ow_tp_mongodb_205236"]["counters"].find(sort=[("_id",1)])]
json.dump(out, open(sys.argv[1],"w"), indent=1); print(json.dumps(out, indent=1))
