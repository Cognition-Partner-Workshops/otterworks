import os, pymongo, json
c=pymongo.MongoClient(os.environ["MONGODB_ATLAS_URI"], serverSelectionTimeoutMS=15000)
db=c["ow_tp_mongodb_205236"]; q=c["ow_tp_mongodb_205236_quarantine"]
cols=["subscriptions","subscriptions_history","usage_events","rating_periods","billing_invoices","credit_notes","dunning_attempts","notifications","billing_audit_log"]
out={k:db[k].count_documents({}) for k in cols}
out["sum_results_len"]=next(db.rating_periods.aggregate([{"$group":{"_id":None,"n":{"$sum":{"$size":{"$ifNull":["$results",[]]}}}}}]),{}).get("n")
out["sum_lines_len"]=next(db.billing_invoices.aggregate([{"$group":{"_id":None,"n":{"$sum":{"$size":{"$ifNull":["$lines",[]]}}}}}]),{}).get("n")
out["staging_residue"]=[n for n in db.list_collection_names() if "__staging" in n]
out["quarantine_u5_collections"]=[n for n in q.list_collection_names() if n in cols]
out["quarantine_all"]={n:q[n].count_documents({}) for n in q.list_collection_names()}
out["audit_log_ids"]=[d["_id"] for d in db.billing_audit_log.find({},{"_id":1})]
out["shared_refs"]={k:db[k].count_documents({}) for k in ["codes","tenants","plans"]}
print(json.dumps(out,default=str,indent=1))
