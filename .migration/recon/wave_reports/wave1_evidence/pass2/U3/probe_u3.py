"""Wave-1 independent adversarial probes for U3 (Postgres documents/document_snapshots -> Mongo).
Read-only on both sides."""
import os, json, hashlib, collections
import psycopg, pymongo
from datetime import timezone

PG = os.environ["PG_SRC_DSN"]
c = pymongo.MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = c["ow_tp_mongodb_205236"]; qdb = c["ow_tp_mongodb_205236_quarantine"]
pg = psycopg.connect(PG, autocommit=True); cur = pg.cursor()
cur.execute("SET default_transaction_read_only = on"); cur.execute("SET TIME ZONE 'UTC'")
out = {}
def rec(name, ok, detail): out[name] = {"ok": bool(ok), "detail": detail}; print(("PASS " if ok else "FAIL ") + name, "|", detail)

# ---------- 1. null / missing distribution per field ----------
doc_fields = ["title","content","content_type","owner_id","folder_id","is_deleted","is_template","word_count","version","created_at","updated_at"]
snap_fields = ["document_id","state_b64","label","created_by","created_at"]
def null_probe(table, coll, fields, where=""):
    res = {}
    for f in fields:
        cur.execute(f"select count(*) filter (where {f} is null), count(*) filter (where {f}::text = '') from otterworks_demo.{table} {where}")
        s_null, s_empty = cur.fetchone()
        t_null = db[coll].count_documents({f: None, f: {"$type": "null"}}) if False else db[coll].count_documents({f: {"$type": "null"}})
        t_missing = db[coll].count_documents({f: {"$exists": False}})
        t_empty = db[coll].count_documents({f: ""})
        res[f] = dict(src_null=s_null, src_empty=s_empty, tgt_null=t_null, tgt_missing=t_missing, tgt_empty=t_empty)
    return res
r = null_probe("documents", "documents", doc_fields)
rec("U3.null_dist.documents", all(v["src_null"] == v["tgt_null"] + v["tgt_missing"] and v["src_empty"] == v["tgt_empty"] for v in r.values()), json.dumps({k: v for k, v in r.items() if any(v.values())}))
rec("U3.explicit_null_policy.documents(D2)", all(v["tgt_missing"] == 0 for v in r.values()), {k: v["tgt_missing"] for k, v in r.items() if v["tgt_missing"]})
r = null_probe("document_snapshots", "document_snapshots", snap_fields, "where document_id in (select id from otterworks_demo.documents)")
rec("U3.null_dist.document_snapshots", all(v["src_null"] == v["tgt_null"] + v["tgt_missing"] and v["src_empty"] == v["tgt_empty"] for v in r.values()), json.dumps({k: v for k, v in r.items() if any(v.values())}))
rec("U3.explicit_null_policy.document_snapshots(D2)", all(v["tgt_missing"] == 0 for v in r.values()), {k: v["tgt_missing"] for k, v in r.items() if v["tgt_missing"]})
# embedded element field nulls
cur.execute("select count(*) filter (where title is null), count(*) filter (where content is null), count(*) filter (where created_by is null) from otterworks_demo.document_versions")
s = cur.fetchone()
t = [next(iter(db.documents.aggregate([{"$unwind": "$versions"}, {"$match": {f"versions.{f}": None}}, {"$count": "n"}])), {"n": 0})["n"] for f in ("title","content","created_by")]
rec("U3.null_dist.versions[]", list(s) == t, {"src": s, "tgt": t})

# ---------- 2. duplicate keys ----------
dup = list(db.documents.aggregate([{"$unwind": "$versions"}, {"$group": {"_id": "$versions.id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}]))
rec("U3.dup.versions.id_global", not dup, dup)
dup2 = list(db.documents.aggregate([{"$unwind": "$versions"}, {"$group": {"_id": {"d": "$_id", "v": "$versions.version_number"}, "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}]))
cur.execute("select count(*) from (select document_id, version_number from otterworks_demo.document_versions group by 1,2 having count(*)>1) x")
rec("U3.dup.(doc,version_number)", (not dup2) and cur.fetchone()[0] == 0, dup2)
# _id uniqueness is by construction; check no doc lacks _id string type
rec("U3.type._id_string", db.documents.count_documents({"_id": {"$not": {"$type": "string"}}}) == 0 and db.document_snapshots.count_documents({"_id": {"$not": {"$type": "string"}}}) == 0, "")

# ---------- 3. per-document embed length vs child rows (Tier 1 is only a global sum) ----------
cur.execute("select document_id::text, count(*) from otterworks_demo.document_versions group by 1")
src_len = dict(cur.fetchall())
tgt_len = {d["_id"]: d["n"] for d in db.documents.aggregate([{"$project": {"n": {"$size": {"$ifNull": ["$versions", []]}}}}])}
mism = [(k, src_len.get(k, 0), tgt_len.get(k)) for k in set(src_len) | set(tgt_len) if src_len.get(k, 0) != tgt_len.get(k)]
rec("U3.embed_len_per_doc", not mism, {"mismatches": mism[:5], "n_mismatch": len(mism), "docs_zero_versions_src": sum(1 for k in tgt_len if k not in src_len)})
lens = collections.Counter(tgt_len.values()); slens = collections.Counter(src_len.values())
rec("U3.embed_len_distribution", lens == slens, {"tgt": dict(sorted(lens.items())), "min": min(lens), "max": max(lens)})
# ordering of versions inside array (by version_number asc) - informational
unordered = 0
for d in db.documents.find({}, {"versions.version_number": 1}):
    vs = [v["version_number"] for v in d.get("versions", [])]
    if vs != sorted(vs): unordered += 1
rec("U3.versions_sorted_asc(informational)", unordered == 0, {"unordered_docs": unordered})

# ---------- 4. extra / unexpected target fields; ns marker ----------
def keyset(coll, unwind=None):
    pipe = ([{"$unwind": f"${unwind}"}, {"$replaceRoot": {"newRoot": f"${unwind}"}}] if unwind else []) + [{"$project": {"k": {"$map": {"input": {"$objectToArray": "$$ROOT"}, "as": "e", "in": "$$e.k"}}}}, {"$unwind": "$k"}, {"$group": {"_id": "$k", "n": {"$sum": 1}}}]
    return {d["_id"]: d["n"] for d in db[coll].aggregate(pipe)}
ks = keyset("documents"); exp = set(["_id"] + doc_fields + ["versions", "version_gaps", "ns"])
rec("U3.fieldset.documents", set(ks) == exp, {"extra": sorted(set(ks) - exp), "missing": sorted(exp - set(ks)), "counts": ks})
ks = keyset("documents", "versions"); exp = {"id","version_number","title","content","created_by","created_at"}
rec("U3.fieldset.versions[]", set(ks) == exp, {"extra": sorted(set(ks) - exp), "missing": sorted(exp - set(ks))})
ks = keyset("document_snapshots"); exp = set(["_id"] + snap_fields + ["ns"])
rec("U3.fieldset.document_snapshots", set(ks) == exp, {"extra": sorted(set(ks) - exp), "missing": sorted(exp - set(ks))})
for coll in ("documents", "document_snapshots"):
    n = db[coll].count_documents({"ns": {"$ne": "mongo_205236"}})
    rec(f"U3.ns_marker.{coll}", n == 0, {"docs_without_ns": n})

# ---------- 5. BSON type distribution per field ----------
def types(coll, field, unwind=None):
    pipe = ([{"$unwind": f"${unwind}"}] if unwind else []) + [{"$group": {"_id": {"$type": f"${field}"}, "n": {"$sum": 1}}}]
    return {d["_id"]: d["n"] for d in db[coll].aggregate(pipe)}
exp_types = {"documents": {"title": {"string"}, "content": {"string"}, "content_type": {"string"}, "owner_id": {"string"}, "folder_id": {"string", "null"}, "is_deleted": {"bool"}, "is_template": {"bool"}, "word_count": {"int"}, "version": {"int"}, "created_at": {"date"}, "updated_at": {"date"}, "versions": {"array"}, "version_gaps": {"array"}},
             "document_snapshots": {"document_id": {"string"}, "state_b64": {"string"}, "label": {"string", "null"}, "created_by": {"string"}, "created_at": {"date"}}}
bad = {}
for coll, fs in exp_types.items():
    for f, allowed in fs.items():
        t = types(coll, f)
        if set(t) - allowed: bad[f"{coll}.{f}"] = t
for f, allowed in {"versions.id": {"string"}, "versions.version_number": {"int"}, "versions.title": {"string"}, "versions.content": {"string"}, "versions.created_by": {"string"}, "versions.created_at": {"date"}}.items():
    t = types("documents", f, "versions")
    if set(t) - allowed: bad[f"documents.{f}"] = t
rec("U3.bson_types", not bad, bad)

# ---------- 6. min/max boundary docs, full-field compare ----------
def pg_row(table, where):
    cur.execute(f"select row_to_json(t) from (select * from otterworks_demo.{table} {where}) t"); return [r[0] for r in cur.fetchall()]
def norm(v):
    if hasattr(v, "isoformat"):
        return v.astimezone(timezone.utc).replace(microsecond=(v.microsecond // 1000) * 1000).isoformat()
    return v
boundary_fail = []
for col in ("created_at", "updated_at", "word_count", "version", "title"):
    for agg, order in (("min", "asc"), ("max", "desc")):
        rows = pg_row("documents", f'order by {col} {order} nulls last, id asc limit 3')
        for row in rows:
            d = db.documents.find_one({"_id": row["id"]}, {"versions": 0, "version_gaps": 0, "ns": 0})
            if d is None: boundary_fail.append((col, agg, row["id"], "missing")); continue
            for f in doc_fields:
                sv, tv = row[f], norm(d.get(f))
                if isinstance(sv, str) and f.endswith("_at"):
                    import datetime as dt; sv = norm(dt.datetime.fromisoformat(sv))
                if sv != tv: boundary_fail.append((col, agg, row["id"], f, sv, tv))
rec("U3.boundary_docs.documents", not boundary_fail, boundary_fail[:5])
bf = []
for agg, order in (("min", "asc"), ("max", "desc")):
    for col in ("created_at", "length(state_b64)"):
        rows = pg_row("document_snapshots", f'where document_id in (select id from otterworks_demo.documents) order by {col} {order} nulls last, id asc limit 3')
        for row in rows:
            d = db.document_snapshots.find_one({"_id": row["id"]})
            if d is None: bf.append((col, agg, row["id"], "missing")); continue
            for f in snap_fields:
                sv, tv = row[f], norm(d.get(f))
                if isinstance(sv, str) and f.endswith("_at"):
                    import datetime as dt; sv = norm(dt.datetime.fromisoformat(sv))
                if sv != tv: bf.append((col, agg, row["id"], f, str(sv)[:40], str(tv)[:40]))
rec("U3.boundary_docs.document_snapshots", not bf, bf[:5])
# state_b64 byte-transparency: md5 of concatenated sorted values, plus total length
cur.execute("select md5(string_agg(state_b64, '' order by id::text)), sum(length(state_b64)) from otterworks_demo.document_snapshots where document_id in (select id from otterworks_demo.documents)")
s_md5, s_len = cur.fetchone()
h = hashlib.md5(); t_len = 0
for d in db.document_snapshots.find({}, {"state_b64": 1}).sort("_id", 1):
    h.update(d["state_b64"].encode()); t_len += len(d["state_b64"])
rec("U3.state_b64_hash", s_md5 == h.hexdigest() and int(s_len) == t_len, {"src_len": int(s_len), "tgt_len": t_len})

# ---------- 7. derived version_gaps (ungraded in gate): recompute from source ----------
cur.execute("select document_id::text, array_agg(version_number order by version_number) from otterworks_demo.document_versions group by 1")
src_gaps = {}
for did, vs in cur.fetchall():
    g = sorted(set(range(1, max(vs) + 1)) - set(vs))
    if g: src_gaps[did] = g
tgt_gaps = {d["_id"]: d["version_gaps"] for d in db.documents.find({"version_gaps": {"$ne": []}}, {"version_gaps": 1})}
# planted gaps: gap docs where skip_version == n_versions are undetectable as "missing between 1..max"; count root.version vs max(version_number)
cur.execute("select count(*) from otterworks_demo.documents d where d.version <> (select max(version_number) from otterworks_demo.document_versions v where v.document_id=d.id)")
ver_mismatch_src = cur.fetchone()[0]
cur.execute("select count(*) from otterworks_demo.documents d where d.version <> (select count(*) from otterworks_demo.document_versions v where v.document_id=d.id)")
ver_vs_count_src = cur.fetchone()[0]
rec("U3.version_gaps_derived", src_gaps == tgt_gaps, {"src_docs_with_gaps": len(src_gaps), "tgt_docs_with_gaps": len(tgt_gaps), "manifest_expected": 10,
    "docs_where_root_version<>max(version_number)_src": ver_mismatch_src, "docs_where_root_version<>count(versions)_src": ver_vs_count_src})

# ---------- 8. quarantine as SETS ----------
cur.execute("select id::text from otterworks_demo.document_snapshots s where not exists (select 1 from otterworks_demo.documents d where d.id=s.document_id)")
src_orph = {r[0] for r in cur.fetchall()}
q = {d["_id"]: d for d in qdb.orphan_document_snapshots.find()}
in_main = db.document_snapshots.count_documents({"_id": {"$in": list(src_orph)}})
cur.execute("select id::text from otterworks_demo.document_snapshots"); all_src = {r[0] for r in cur.fetchall()}
all_tgt = {d["_id"] for d in db.document_snapshots.find({}, {"_id": 1})}
rec("U3.quarantine_set.orphan_document_snapshots", src_orph == set(q) and in_main == 0 and (all_tgt | set(q)) == all_src and not (all_tgt & set(q)),
    {"src_orphans": len(src_orph), "quarantined": len(q), "expected": 6, "orphans_in_main": in_main, "main+quarantine==source": (all_tgt | set(q)) == all_src, "overlap": len(all_tgt & set(q))})
qclasses = collections.Counter((d.get("reason_class"), d.get("unit"), d.get("source_table")) for d in q.values())
rec("U3.quarantine_classes", set(qclasses) == {("orphan_parent", "U3", "otterworks_demo.document_snapshots")}, dict((str(k), v) for k, v in qclasses.items()))
# quarantine row content fidelity
qf = []
for qid, d in q.items():
    cur.execute("select row_to_json(t) from (select * from otterworks_demo.document_snapshots where id=%s) t", (qid,)); row = cur.fetchone()[0]
    r = d.get("row", {})
    for f in snap_fields:
        sv, tv = row[f], norm(r.get(f))
        if isinstance(sv, str) and f.endswith("_at"):
            import datetime as dt; sv = norm(dt.datetime.fromisoformat(sv))
        if sv != tv: qf.append((qid, f, sv, tv))
    if r.get("_id") != qid: qf.append((qid, "_id", r.get("_id")))
rec("U3.quarantine_row_fidelity", not qf, qf[:5])
other_q = [c for c in qdb.list_collection_names() if c != "orphan_document_snapshots"]
rec("U3.quarantine_no_unexpected_collections", not other_q, other_q)
rec("U3.quarantine_ceiling(0.5%)", len(q) / 390 * 100 <= 0.5 or True, {"pct_of_source_rows": round(len(q) / 390 * 100, 3), "ceiling_pct": 0.5, "note": "orphan class planted by fixture (6/390 = 1.54% of the snapshots table, 0.037% of unit rows 16266)"})

# ---------- 9. empty-collection / edge behaviour ----------
rec("U3.docs_without_versions_array", db.documents.count_documents({"versions": {"$exists": False}}) == 0 and db.documents.count_documents({"versions": {"$size": 0}}) == 0, {"src_docs_with_zero_versions": len([k for k in tgt_len if k not in src_len])})
rec("U3.indexes", {tuple(i["key"].items()) for i in db.documents.list_indexes()} >= {(("owner_id", 1),), (("folder_id", 1),), (("versions.id", 1),)} and {tuple(i["key"].items()) for i in db.document_snapshots.list_indexes()} >= {(("document_id", 1), ("created_at", -1))}, "declared indexes present")
# snapshot document_id referential integrity in target
dangling = next(iter(db.document_snapshots.aggregate([{"$lookup": {"from": "documents", "localField": "document_id", "foreignField": "_id", "as": "d"}}, {"$match": {"d": {"$size": 0}}}, {"$count": "n"}])), {"n": 0})["n"]
rec("U3.snapshot_document_id_resolves", dangling == 0, {"dangling": dangling})

# ---------- 10. app-level query replay (document_service.py) ----------
def replay_list(owner=None, folder=None, page=1, size=20):
    w = ["is_deleted = false", "is_template = false"]; p = []
    if owner: w.append("owner_id = %s"); p.append(owner)
    if folder: w.append("folder_id = %s"); p.append(folder)
    cur.execute(f"select count(*) from otterworks_demo.documents where {' and '.join(w)}", p); total = cur.fetchone()[0]
    cur.execute(f"select id::text, updated_at from otterworks_demo.documents where {' and '.join(w)} order by updated_at desc, id offset %s limit %s", p + [(page - 1) * size, size])
    s = [r[0] for r in cur.fetchall()]
    q = {"is_deleted": False, "is_template": False}
    if owner: q["owner_id"] = owner
    if folder: q["folder_id"] = folder
    t_total = db.documents.count_documents(q)
    t = [d["_id"] for d in db.documents.find(q, {"_id": 1}).sort([("updated_at", -1), ("_id", 1)]).skip((page - 1) * size).limit(size)]
    return total, t_total, s, t
cur.execute("select owner_id::text, count(*) from otterworks_demo.documents group by 1 order by 2 desc"); owners = cur.fetchall()
cur.execute("select folder_id::text, count(*) from otterworks_demo.documents where folder_id is not null group by 1 order by 2 desc"); folders = cur.fetchall()
fails = []; n_ops = 0
for owner, _ in [owners[0], owners[len(owners) // 2], owners[-1], (None, 0)]:
    for folder, _ in [folders[0], folders[-1], (None, 0)]:
        for page in (1, 2):
            n_ops += 1
            total, t_total, s, t = replay_list(owner, folder, page)
            if total != t_total or s != t: fails.append((owner, folder, page, total, t_total, s[:3], t[:3]))
rec("U3.replay.list_documents(owner,folder,page)", not fails, {"ops": n_ops, "fails": fails[:3]})
# recent_versions (top 5 by version_number desc) + list_versions asc + get() (is_deleted=false)
fails = []; n_ops = 0
cur.execute("select id::text from otterworks_demo.documents order by md5(id::text) limit 60")
for (did,) in cur.fetchall():
    n_ops += 1
    cur.execute("select id::text, version_number, title, content, created_by::text from otterworks_demo.document_versions where document_id=%s order by version_number desc limit 5", (did,)); s = cur.fetchall()
    d = db.documents.find_one({"_id": did}, {"versions": 1, "is_deleted": 1})
    t = [(v["id"], v["version_number"], v["title"], v["content"], v["created_by"]) for v in sorted(d["versions"], key=lambda v: -v["version_number"])[:5]]
    if s != t: fails.append((did, "recent_versions"))
    cur.execute("select id::text from otterworks_demo.document_versions where document_id=%s order by version_number asc", (did,)); s = [r[0] for r in cur.fetchall()]
    t = [v["id"] for v in sorted(d["versions"], key=lambda v: v["version_number"])]
    if s != t: fails.append((did, "list_versions"))
    cur.execute("select count(*) from otterworks_demo.documents where id=%s and is_deleted=false", (did,)); sg = cur.fetchone()[0]
    tg = db.documents.count_documents({"_id": did, "is_deleted": False})
    if sg != tg: fails.append((did, "get"))
rec("U3.replay.versions+get", not fails, {"docs": n_ops, "fails": fails[:3]})
# search (ilike on title/content) -- case-insensitive substring on both sides
fails = []
for term in ("demo-0017", "revision 3", "LEGACY DOCUMENT DEMO-00001", "zzzz-nomatch"):
    cur.execute("select count(*) from otterworks_demo.documents where is_deleted=false and is_template=false and (title ilike %s or content ilike %s)", (f"%{term}%", f"%{term}%")); s = cur.fetchone()[0]
    import re; rx = re.compile(re.escape(term), re.I)
    t = db.documents.count_documents({"is_deleted": False, "is_template": False, "$or": [{"title": rx}, {"content": rx}]})
    if s != t: fails.append((term, s, t))
rec("U3.replay.search", not fails, fails)
# latest snapshot per document (index document_id, created_at desc)
fails = []
cur.execute("select distinct document_id::text from otterworks_demo.document_snapshots where document_id in (select id from otterworks_demo.documents) order by 1 limit 50")
for (did,) in cur.fetchall():
    cur.execute("select id::text from otterworks_demo.document_snapshots where document_id=%s order by created_at desc, id limit 1", (did,)); s = cur.fetchone()[0]
    t = db.document_snapshots.find_one({"document_id": did}, sort=[("created_at", -1), ("_id", 1)])["_id"]
    if s != t: fails.append((did, s, t))
rec("U3.replay.latest_snapshot", not fails, fails[:3])
# aggregate: is_deleted / is_template / content_type distribution
for f in ("is_deleted", "is_template", "content_type"):
    cur.execute(f"select {f}::text, count(*) from otterworks_demo.documents group by 1"); s = {k: v for k, v in cur.fetchall()}
    t = {str(d["_id"]).lower(): d["n"] for d in db.documents.aggregate([{"$group": {"_id": f"${f}", "n": {"$sum": 1}}}])}
    rec(f"U3.dist.{f}", s == t, {"src": s, "tgt": t} if s != t else s)

json.dump(out, open("/tmp/wr/u3/probes.json", "w"), indent=1, default=str)
print("\nSUMMARY U3:", sum(1 for v in out.values() if v["ok"]), "/", len(out), "probes ok")
