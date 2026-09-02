import os, pymongo
c=pymongo.MongoClient(os.environ["MONGODB_ATLAS_URI"])
db=c["ow_tp_mongodb_205236"]; q=c["ow_tp_mongodb_205236_quarantine"]
for n in ["customers","customers_history","counters","documents","document_snapshots","files"]:
    print(n, db[n].estimated_document_count(), db[n].count_documents({}))
print("quarantine:", {n:q[n].count_documents({}) for n in q.list_collection_names()})
print("customers attrs total:", list(db.customers.aggregate([{"$project":{"n":{"$size":{"$ifNull":["$attributes",[]]}}}},{"$group":{"_id":None,"s":{"$sum":"$n"}}}])))
print("versions total:", list(db.documents.aggregate([{"$project":{"n":{"$size":{"$ifNull":["$versions",[]]}}}},{"$group":{"_id":None,"s":{"$sum":"$n"}}}])))
print("counters:", list(db.counters.find({},{"_id":1,"seq":1,"value":1})))
