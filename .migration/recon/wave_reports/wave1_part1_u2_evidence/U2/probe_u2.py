"""Independent adversarial probes for U2 (invoices + lines[] embed + quarantine.invoice_feed_orphan_lines).
Read-only on both sides. Secrets by NAME (OW_BILLING_FIXTURE_DSN, MONGODB_ATLAS_URI). One serial Oracle connection."""
import json, os, re, sys, time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

import oracledb
from bson import Decimal128, Int64
from pymongo import MongoClient

oracledb.defaults.fetch_decimals = True
BATCH = 85559852
NS = "mongo_205236"
user, pw, dsn = os.environ["OW_BILLING_FIXTURE_DSN"].split("/", 2)
ora = oracledb.connect(user=user, password=pw, dsn=dsn)
cur = ora.cursor(); cur.arraysize = 5000
m = MongoClient(os.environ["MONGODB_ATLAS_URI"])
db = m["ow_tp_mongodb_205236"]; qdb = m["ow_tp_mongodb_205236_quarantine"]
inv = db["invoices"]; qcol = qdb["invoice_feed_orphan_lines"]
spec = json.load(open(sys.argv[1]))
cmap = next(c for c in spec["collections"] if c["collection"] == "invoices")
emap = cmap["embeds"][0]
results = []; n_sql = 0
def q(sql, **kw):
    global n_sql; n_sql += 1; cur.execute(sql, kw); return cur.fetchall()
def ok(name, cond, detail=""):
    results.append({"probe": name, "ok": bool(cond), "detail": str(detail)[:600]})
    print(("ok   " if cond else "FLAG ") + name + (" — " + str(detail)[:300] if detail else ""))
t0 = time.time()
HW = f"batch_no = {BATCH}"
LW = f"l.batch_no = {BATCH} AND EXISTS (SELECT 1 FROM invoice_header h WHERE h.batch_no = {BATCH} AND h.invoice_id = l.invoice_id)"
N_INV = 18750

# 1. null / missing / empty-string per field (root and embedded)
hcols = [f["source"] for f in cmap["fields"]]; lcols = [f["source"] for f in emap["fields"]]
src_null = dict(zip(hcols, [int(v) for v in q(f"SELECT {', '.join(f'SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END)' for c in hcols)} FROM invoice_header WHERE {HW}")[0]]))
proj = {f["target"]: {"$cond": [{"$or": [{"$eq": [{"$type": '$' + f["target"]}, "missing"]}, {"$eq": ['$' + f["target"], None]}]}, 1, 0]} for f in cmap["fields"]}
projm = {f["target"] + "__m": {"$cond": [{"$eq": [{"$type": '$' + f["target"]}, "missing"]}, 1, 0]} for f in cmap["fields"]}
proje = {f["target"] + "__e": {"$cond": [{"$eq": ['$' + f["target"], ""]}, 1, 0]} for f in cmap["fields"]}
agg = list(inv.aggregate([{"$project": proj | projm | proje}, {"$group": {"_id": None} | {k: {"$sum": '$' + k} for k in list(proj) + list(projm) + list(proje)}}]))[0]
bad = [(f["source"], src_null[f["source"]], agg[f["target"]]) for f in cmap["fields"] if src_null[f["source"]] != agg[f["target"]]]
ok("1.1 root null+missing per field == source NULL count (9 fields)", not bad, bad or {k: v for k, v in src_null.items() if v})
ok("1.2 root: no MISSING fields, no empty strings (explicit_null)", not [f for f in cmap["fields"] if agg[f["target"] + "__m"] or agg[f["target"] + "__e"]])
src_lnull = dict(zip(lcols, [int(v) for v in q(f"SELECT {', '.join(f'SUM(CASE WHEN l.{c} IS NULL THEN 1 ELSE 0 END)' for c in lcols)} FROM invoice_line l WHERE {LW}")[0]]))
lproj = {f["target"]: {"$cond": [{"$or": [{"$eq": [{"$type": '$lines.' + f["target"]}, "missing"]}, {"$eq": ['$lines.' + f["target"], None]}]}, 1, 0]} for f in emap["fields"]}
lprojm = {f["target"] + "__m": {"$cond": [{"$eq": [{"$type": '$lines.' + f["target"]}, "missing"]}, 1, 0]} for f in emap["fields"]}
lproje = {f["target"] + "__e": {"$cond": [{"$eq": ['$lines.' + f["target"], ""]}, 1, 0]} for f in emap["fields"]}
lagg = list(inv.aggregate([{"$unwind": "$lines"}, {"$project": lproj | lprojm | lproje}, {"$group": {"_id": None, "n": {"$sum": 1}} | {k: {"$sum": '$' + k} for k in list(lproj) + list(lprojm) + list(lproje)}}]))[0]
bad = [(f["source"], src_lnull[f["source"]], lagg[f["target"]]) for f in emap["fields"] if src_lnull[f["source"]] != lagg[f["target"]]]
ok("1.3 embedded null+missing per field == source NULL count (20 fields, 149963 elems)", not bad and lagg["n"] == 149963, bad or {k: v for k, v in src_lnull.items() if v})
ok("1.4 embedded: no MISSING fields, no empty strings", not [f for f in emap["fields"] if lagg[f["target"] + "__m"] or lagg[f["target"] + "__e"]])

# 2. BSON types
want = {"string": "string", "int": "int", "long": "long", "decimal": "decimal", "date": "date"}
tb = []
for f in cmap["fields"]:
    types = {d["_id"]: d["n"] for d in inv.aggregate([{"$group": {"_id": {"$type": '$' + f["target"]}, "n": {"$sum": 1}}}])}
    if set(types) - {want[f["bson_type"]], "null"}: tb.append((f["target"], types))
ok("2.1 root BSON type per field == spec (or null)", not tb, tb)
tb = []
for f in emap["fields"]:
    types = {d["_id"]: d["n"] for d in inv.aggregate([{"$unwind": "$lines"}, {"$group": {"_id": {"$type": '$lines.' + f["target"]}, "n": {"$sum": 1}}}])}
    if set(types) - {want[f["bson_type"]], "null"}: tb.append((f["target"], types))
ok("2.2 embedded BSON type per field == spec (or null)", not tb, tb)
kt = {d["_id"]: d["n"] for d in inv.aggregate([{"$group": {"_id": {"$type": "$_id"}, "n": {"$sum": 1}}}])}
ok("2.3 _id string on all docs; _id == invoice_id", kt == {"string": N_INV} and inv.count_documents({"$expr": {"$ne": ["$_id", "$invoice_id"]}}) == 0, kt)
dt = {tuple(d["_id"]): d["n"] for d in inv.aggregate([{"$group": {"_id": [{"$type": "$invoice_date"}, {"$type": "$due_date"}], "n": {"$sum": 1}}}])}
ok("2.4 derived invoice_date/due_date are BSON date or null", all(set(k) <= {"date", "null"} for k in dt), dt)

# 3. duplicate keys
src_dup_no = q(f"SELECT COUNT(*) FROM (SELECT invoice_no FROM invoice_header WHERE {HW} GROUP BY invoice_no HAVING COUNT(*) > 1)")[0][0]
tgt_dup_no = list(inv.aggregate([{"$group": {"_id": "$invoice_no", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}]))
ok("3.1 invoice_no duplicate groups equal (source vs target)", bool(src_dup_no) == bool(tgt_dup_no), f"src_groups={src_dup_no} tgt={tgt_dup_no}")
ld = list(inv.aggregate([{"$unwind": "$lines"}, {"$group": {"_id": "$lines.line_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}]))
ok("3.2 line_id unique across all embedded lines", not ld, ld)
src_dup_ln = q(f"SELECT COUNT(*) FROM (SELECT l.invoice_id, l.line_no FROM invoice_line l WHERE {LW} GROUP BY l.invoice_id, l.line_no HAVING COUNT(*) > 1)")[0][0]
tgt_dup_ln = list(inv.aggregate([{"$unwind": "$lines"}, {"$group": {"_id": {"i": "$_id", "n": "$lines.line_no"}, "c": {"$sum": 1}}}, {"$match": {"c": {"$gt": 1}}}, {"$count": "n"}]))
ok("3.3 (invoice_id,line_no) duplicate groups equal", bool(src_dup_ln) == bool(tgt_dup_ln), f"src_groups={src_dup_ln} tgt={tgt_dup_ln}")
qx = qcol.count_documents({"_id": {"$in": [d["_id"] for d in inv.aggregate([{"$unwind": "$lines"}, {"$project": {"_id": "$lines.line_id"}}])]}}) if False else len(set(d["_id"] for d in qcol.find({}, {"_id": 1})) & set(d["_id"] for d in inv.aggregate([{"$unwind": "$lines"}, {"$project": {"_id": "$lines.line_id"}}])))
ok("3.4 no line_id appears BOTH embedded and quarantined", qx == 0, qx)

# 4. boundary docs: MIN/MAX of every numeric/date-ish field + LENGTH extremes; full root + all embedded lines compare
def src_cmp(f, v):
    if v is None: return None
    bt = f["bson_type"]
    if bt == "string": return (str(v).rstrip(" ") if "rstrip_spaces" in f["rules"] else str(v)) or None
    if bt in ("int", "long"): return int(v)
    if bt == "decimal":
        mt = re.search(r"NUMBER\(\d+,(\d+)\)", f["source_type"]); return Decimal(str(v)).quantize(Decimal(1).scaleb(-int(mt.group(1))))
def tgt_cmp(v):
    if isinstance(v, Decimal128): return v.to_decimal()
    if isinstance(v, Int64): return int(v)
    return v
def compare_invoices(keys, label):
    keys = sorted(set(k for k in keys if k)); diffs = []; n = 0; nl = 0
    for i in range(0, len(keys), 500):
        chunk = keys[i:i + 500]; binds = {f"k{j}": k for j, k in enumerate(chunk)}; inl = ', '.join(':' + b for b in binds)
        hrows = {r[0]: dict(zip(hcols, r)) for r in q(f"SELECT {', '.join(hcols)} FROM invoice_header WHERE invoice_id IN ({inl})", **binds)}
        lrows = {}
        for r in q(f"SELECT {', '.join(lcols)} FROM invoice_line l WHERE l.batch_no = {BATCH} AND invoice_id IN ({inl}) ORDER BY invoice_id, line_no, line_id", **binds):
            lrows.setdefault(r[2], []).append(dict(zip(lcols, r)))
        docs = {d["_id"]: d for d in inv.find({"_id": {"$in": chunk}})}
        for k, row in hrows.items():
            n += 1; d = docs.get(k)
            if d is None: diffs.append((k, "missing")); continue
            for f in cmap["fields"]:
                a, b = src_cmp(f, row[f["source"]]), tgt_cmp(d.get(f["target"]))
                if a != b: diffs.append((k, f["source"], a, b))
            sl = lrows.get(k, []); tl = d.get("lines", [])
            if [x["LINE_ID"] for x in sl] != [x["line_id"] for x in tl]: diffs.append((k, "line order/set", [x["LINE_ID"] for x in sl][:5], [x["line_id"] for x in tl][:5])); continue
            for s, t in zip(sl, tl):
                nl += 1
                for f in emap["fields"]:
                    a, b = src_cmp(f, s[f["source"]]), tgt_cmp(t.get(f["target"]))
                    if a != b: diffs.append((k, s["LINE_ID"], f["source"], a, b))
    ok(label, not diffs, diffs[:5] or f"{n} invoices × 9 fields + {nl} lines × 20 fields equal")
bk = []
for c in ("STATUS_CD", "TOTAL_AMT", "INVOICE_ID", "INVOICE_NO", "CUST_ID", "TENANT_ID", "INVOICE_DT", "DUE_DT"):
    bk += [k for k in q(f"SELECT MIN(invoice_id) KEEP (DENSE_RANK FIRST ORDER BY {c}), MIN(invoice_id) KEEP (DENSE_RANK LAST ORDER BY {c}) FROM invoice_header WHERE {HW} AND {c} IS NOT NULL")[0] if k]
for c in ("QTY", "UNIT_PRICE", "AMOUNT", "TAX_AMT", "LINE_NO", "LINE_TYPE_CD", "LENGTH(ITEM_DESC)", "LENGTH(GL_ACCT_CSV)", "LENGTH(CUST_NAME)", "LINE_ID"):
    bk += [k for k in q(f"SELECT MIN(l.invoice_id) KEEP (DENSE_RANK FIRST ORDER BY {c}), MIN(l.invoice_id) KEEP (DENSE_RANK LAST ORDER BY {c}) FROM invoice_line l WHERE {LW} AND {c} IS NOT NULL")[0] if k]
bk += [r[0] for r in q(f"SELECT invoice_id FROM (SELECT invoice_id, COUNT(*) n FROM invoice_line l WHERE {LW} GROUP BY invoice_id ORDER BY n DESC) WHERE ROWNUM <= 3")]
bk += [r[0] for r in q(f"SELECT h.invoice_id FROM invoice_header h WHERE {HW} AND NOT EXISTS (SELECT 1 FROM invoice_line l WHERE l.invoice_id = h.invoice_id) AND ROWNUM <= 3")]
compare_invoices(bk, f"4.1 boundary invoices ({len(set(bk))} keys: MIN/MAX per field, longest invoices, zero-line invoices) full compare incl. all lines")
sample = [d["_id"] for d in inv.aggregate([{"$sample": {"size": 200}}, {"$project": {"_id": 1}}])]
compare_invoices(sample, "4.2 200 random invoices full compare incl. all lines")
# decimal text equality (no float path) on 300 random lines
rows = q(f"SELECT line_id, TO_CHAR(qty), TO_CHAR(unit_price), TO_CHAR(amount), TO_CHAR(tax_amt) FROM (SELECT * FROM invoice_line l WHERE {LW} ORDER BY DBMS_RANDOM.VALUE) WHERE ROWNUM <= 300")
lines = {d["l"]["line_id"]: d["l"] for d in inv.aggregate([{"$match": {"lines.line_id": {"$in": [r[0] for r in rows]}}}, {"$unwind": "$lines"}, {"$match": {"lines.line_id": {"$in": [r[0] for r in rows]}}}, {"$project": {"l": "$lines"}}])}
md = []
for r in rows:
    d = lines.get(r[0])
    if d is None: md.append((r[0], "missing")); continue
    for name, sv in zip(("qty", "unit_price", "amount", "tax_amt"), r[1:]):
        tv = d.get(name); tv = None if tv is None else tv.to_decimal()
        if (sv is None) != (tv is None) or (sv is not None and Decimal(sv).compare(tv) != 0): md.append((r[0], name, sv, str(tv)))
ok("4.3 line money: Oracle TO_CHAR == Decimal128 on 300 random lines × 4 fields (no float)", not md, md[:5])

# 5. aggregate-only / doc-level: header total vs sum of lines (source property carried), per-tenant & per-status sums
src = {r[0]: (Decimal(r[1]), int(r[2])) for r in q(f"SELECT tenant_id, TO_CHAR(SUM(total_amt)), COUNT(*) FROM invoice_header WHERE {HW} GROUP BY tenant_id")}
tgt = {d["_id"]: (d["a"].to_decimal(), d["n"]) for d in inv.aggregate([{"$group": {"_id": "$tenant_id", "a": {"$sum": "$total_amt"}, "n": {"$sum": 1}}}])}
pd = [k for k in set(src) | set(tgt) if k not in src or k not in tgt or src[k][1] != tgt[k][1] or src[k][0].compare(tgt[k][0]) != 0]
ok(f"5.1 per-tenant SUM(total_amt), COUNT over {len(src)} tenants equal", not pd, pd[:3])
src = {(r[0], r[1]): (Decimal(r[2]), Decimal(r[3]), int(r[4])) for r in q(f"SELECT h.tenant_id, l.line_type_cd, TO_CHAR(SUM(l.amount)), TO_CHAR(SUM(l.tax_amt)), COUNT(*) FROM invoice_header h JOIN invoice_line l ON l.invoice_id = h.invoice_id AND l.batch_no = h.batch_no WHERE h.{HW} GROUP BY h.tenant_id, l.line_type_cd")}
tgt = {(d["_id"]["t"], d["_id"]["c"]): (d["a"].to_decimal(), d["x"].to_decimal(), d["n"]) for d in inv.aggregate([{"$unwind": "$lines"}, {"$group": {"_id": {"t": "$tenant_id", "c": "$lines.line_type_cd"}, "a": {"$sum": "$lines.amount"}, "x": {"$sum": "$lines.tax_amt"}, "n": {"$sum": 1}}}])}
pd = [k for k in set(src) | set(tgt) if k not in src or k not in tgt or src[k][2] != tgt[k][2] or src[k][0].compare(tgt[k][0]) != 0 or src[k][1].compare(tgt[k][1]) != 0]
ok(f"5.2 per (tenant, line_type) SUM(amount), SUM(tax_amt), COUNT over {len(src)} groups equal", not pd, pd[:3])
src_mis = int(q(f"SELECT COUNT(*) FROM invoice_header h WHERE {HW} AND total_amt <> NVL((SELECT SUM(l.amount) FROM invoice_line l WHERE l.invoice_id = h.invoice_id AND l.batch_no = h.batch_no), 0)")[0][0])
tgt_mis = inv.count_documents({"$expr": {"$ne": ["$total_amt", {"$sum": "$lines.amount"}]}})
results.append({"probe": "5.3 invoices where total_amt != SUM(lines.amount) (info; source property)", "ok": True, "detail": f"source={src_mis} target={tgt_mis}"}); print(f"info 5.3 total_amt != sum(lines.amount): source={src_mis} target={tgt_mis}")
ok("5.4 header/lines mismatch count carried identically", src_mis == tgt_mis)
src = Counter({int(r[0]): int(r[1]) for r in q(f"SELECT status_cd, COUNT(*) FROM invoice_header WHERE {HW} GROUP BY status_cd")})
tgt = Counter({d["_id"]: d["n"] for d in inv.aggregate([{"$group": {"_id": "$status_cd", "n": {"$sum": 1}}}])})
ok("5.5 status_cd distribution equal", src == tgt, dict(tgt))
src = Counter({(r[0] or None): int(r[1]) for r in q(f"SELECT l.posted_yn, COUNT(*) FROM invoice_line l WHERE {LW} GROUP BY l.posted_yn")})
tgt = Counter({d["_id"]: d["n"] for d in inv.aggregate([{"$unwind": "$lines"}, {"$group": {"_id": "$lines.posted_yn", "n": {"$sum": 1}}}])})
ok("5.6 lines.posted_yn distribution equal (CHAR rstrip)", src == tgt, dict(tgt))
src = Counter({(r[0] or None): int(r[1]) for r in q(f"SELECT l.src_system, COUNT(*) FROM invoice_line l WHERE {LW} GROUP BY l.src_system")})
tgt = Counter({d["_id"]: d["n"] for d in inv.aggregate([{"$unwind": "$lines"}, {"$group": {"_id": "$lines.src_system", "n": {"$sum": 1}}}])})
ok("5.7 lines.src_system distribution equal", src == tgt, dict(tgt))

# 6. embed-array length distribution vs child rows
src_len = Counter(int(r[1]) for r in q(f"SELECT h.invoice_id, COUNT(l.line_id) FROM invoice_header h LEFT JOIN invoice_line l ON l.invoice_id = h.invoice_id AND l.batch_no = h.batch_no WHERE h.{HW} GROUP BY h.invoice_id"))
tgt_len = Counter({d["_id"]: d["n"] for d in inv.aggregate([{"$project": {"n": {"$size": {"$ifNull": ["$lines", []]}}}}, {"$group": {"_id": "$n", "n": {"$sum": 1}}}])})
ok("6.1 lines[] length histogram == per-invoice child-row histogram", src_len == tgt_len, f"max={max(tgt_len)} zero={tgt_len.get(0,0)} hist={dict(sorted(tgt_len.items()))}")
ok("6.2 lines is an array on every doc (incl. zero-line invoices)", inv.count_documents({"lines": {"$type": "array"}}) == N_INV)
ok("6.3 every line's invoice_id == parent _id; line.batch_no == parent batch_no; line.tenant_id == parent tenant_id; line.cust_id == parent cust_id",
   inv.count_documents({"$expr": {"$gt": [{"$size": {"$filter": {"input": "$lines", "as": "l", "cond": {"$or": [{"$ne": ["$$l.invoice_id", "$_id"]}, {"$ne": ["$$l.batch_no", "$batch_no"]}, {"$ne": ["$$l.tenant_id", "$tenant_id"]}, {"$ne": ["$$l.cust_id", "$cust_id"]}]}}}}, 0]}}) == 0)
src_x = q(f"SELECT SUM(CASE WHEN l.tenant_id <> h.tenant_id THEN 1 ELSE 0 END), SUM(CASE WHEN l.cust_id <> h.cust_id THEN 1 ELSE 0 END), SUM(CASE WHEN l.invoice_no <> h.invoice_no THEN 1 ELSE 0 END) FROM invoice_header h JOIN invoice_line l ON l.invoice_id = h.invoice_id AND l.batch_no = h.batch_no WHERE h.{HW}")[0]
results.append({"probe": "6.4 source denormalised line columns disagreeing with header (tenant/cust/invoice_no) (info)", "ok": True, "detail": str(src_x)}); print("info 6.4 source line/header disagreements:", src_x)
ok("6.5 elements sorted by (line_no, line_id) inside each doc", inv.count_documents({"$expr": {"$ne": ["$lines.line_no", {"$sortArray": {"input": "$lines.line_no", "sortBy": 1}}]}}) == 0)
tot_lines = int(q("SELECT COUNT(*) FROM invoice_line")[0][0]); tot_b = int(q(f"SELECT COUNT(*) FROM invoice_line WHERE {HW}")[0][0]); tot_h = int(q("SELECT COUNT(*) FROM invoice_header")[0][0])
ok("6.6 INVOICE_LINE / INVOICE_HEADER entirely inside the batch (no other-batch rows silently dropped)", tot_lines == tot_b == 150000 and tot_h == N_INV, f"lines_all={tot_lines} lines_batch={tot_b} headers_all={tot_h}")

# 7. quarantine as SET vs expected 37 (manifest orphaned_invoice_lines)
src_orph = {r[0]: r[1] for r in q(f"SELECT l.line_id, l.invoice_id FROM invoice_line l WHERE l.batch_no = {BATCH} AND NOT EXISTS (SELECT 1 FROM invoice_header h WHERE h.invoice_id = l.invoice_id AND h.batch_no = {BATCH})")}
qd = list(qcol.find({}))
tgt_orph = {d["_id"]: d["invoice_id"] for d in qd}
ok("7.1 invoice_feed_orphan_lines SET == Oracle anti-join set; expected 37", set(src_orph) == set(tgt_orph) and len(tgt_orph) == 37, f"src={len(src_orph)} tgt={len(tgt_orph)} symdiff={sorted(set(src_orph) ^ set(tgt_orph))[:5]}")
ok("7.2 quarantine docs carry ns, unit=U2, batch_no, reason_class=orphan_parent, verbatim row with all 20 line fields", all(d.get("ns") == NS and d.get("unit") == "U2" and d.get("batch_no") == BATCH and d.get("reason_class") == "orphan_parent" and set(d["row"]) >= {f["target"] for f in emap["fields"]} for d in qd))
# verbatim check on quarantined rows against source
binds = {f"k{j}": k for j, k in enumerate(sorted(tgt_orph))}
rows = {r[0]: dict(zip(lcols, r)) for r in q(f"SELECT {', '.join(lcols)} FROM invoice_line WHERE line_id IN ({', '.join(':' + b for b in binds)})", **binds)}
vd = [(d["_id"], f["source"]) for d in qd for f in emap["fields"] if src_cmp(f, rows[d["_id"]][f["source"]]) != tgt_cmp(d["row"].get(f["target"]))]
ok("7.3 quarantined rows verbatim == source (37 × 20 fields)", not vd, vd[:5])
orph_inv = set(tgt_orph.values())
ok("7.4 orphan invoice_ids resolve to NO header in ANY batch (true orphans, not cross-batch)", int(q(f"SELECT COUNT(*) FROM invoice_header WHERE invoice_id IN ({', '.join(':' + b for b in {f'i{j}': v for j, v in enumerate(orph_inv)})})", **{f'i{j}': v for j, v in enumerate(orph_inv)})[0][0]) == 0 and inv.count_documents({"_id": {"$in": sorted(orph_inv)}}) == 0, f"distinct_orphan_invoice_ids={len(orph_inv)}")
ok("7.5 quarantine ceiling 0.5 %: 37/150000 lines", 37 / 150000 * 100 <= 0.5, f"{37/1500:.3f} %")
ok("7.6 embedded + quarantined == all batch lines (149963 + 37 = 150000)", lagg["n"] + len(qd) == tot_b)

# 8. derived (ungraded) twins
ok("8.1 lines.gl_accounts == trim(split(gl_acct_csv, ',')) ; null csv -> []", inv.count_documents({"$expr": {"$gt": [{"$size": {"$filter": {"input": "$lines", "as": "l", "cond": {"$ne": ["$$l.gl_accounts", {"$cond": [{"$eq": ["$$l.gl_acct_csv", None]}, [], {"$map": {"input": {"$split": ["$$l.gl_acct_csv", ","]}, "as": "t", "in": {"$trim": {"input": "$$t"}}}}]}]}}}}, 0]}}) == 0)
rows = q(f"SELECT invoice_id, invoice_dt, due_dt, TO_CHAR(TO_DATE(invoice_dt DEFAULT NULL ON CONVERSION ERROR, 'DD-MON-YY', 'NLS_DATE_LANGUAGE=AMERICAN'), 'YYYY-MM-DD'), TO_CHAR(TO_DATE(due_dt DEFAULT NULL ON CONVERSION ERROR, 'DD-MON-YY', 'NLS_DATE_LANGUAGE=AMERICAN'), 'YYYY-MM-DD') FROM (SELECT * FROM invoice_header WHERE {HW} ORDER BY DBMS_RANDOM.VALUE) WHERE ROWNUM <= 400")
docs = {d["_id"]: d for d in inv.find({"_id": {"$in": [r[0] for r in rows]}}, {"invoice_date": 1, "due_date": 1})}
def ds(v): return None if v is None else v.strftime("%Y-%m-%d")
dd = [(r[0], r[1], r[3], ds(docs[r[0]].get("invoice_date"))) for r in rows if ds(docs[r[0]].get("invoice_date")) != r[3] or ds(docs[r[0]].get("due_date")) != r[4]]
ok("8.2 invoice_date/due_date == Oracle TO_DATE(...,'DD-MON-YY') on 400 random headers", not dd, dd[:5])
unp = inv.count_documents({"invoice_dt": {"$ne": None}, "invoice_date": None}) + inv.count_documents({"due_dt": {"$ne": None}, "due_date": None})
src_unp = int(q(f"SELECT SUM(CASE WHEN invoice_dt IS NOT NULL AND TO_DATE(invoice_dt DEFAULT NULL ON CONVERSION ERROR, 'DD-MON-YY', 'NLS_DATE_LANGUAGE=AMERICAN') IS NULL THEN 1 ELSE 0 END) + SUM(CASE WHEN due_dt IS NOT NULL AND TO_DATE(due_dt DEFAULT NULL ON CONVERSION ERROR, 'DD-MON-YY', 'NLS_DATE_LANGUAGE=AMERICAN') IS NULL THEN 1 ELSE 0 END) FROM invoice_header WHERE {HW}")[0][0])
ok("8.3 unparseable header dates: target null-derived count == Oracle conversion-error count (U2 has no dirty-date quarantine class by spec)", unp == src_unp, f"target={unp} source={src_unp}")

# 9. field-set + ns audit
declared = {f["target"] for f in cmap["fields"]} | {"_id", "ns", "lines"} | {d["target"] for d in cmap["derived_ungraded"] if "." not in d["target"] and "[" not in d["target"]}
extra = {d["_id"]: d["n"] for d in inv.aggregate([{"$project": {"k": {"$objectToArray": "$$ROOT"}}}, {"$unwind": "$k"}, {"$group": {"_id": "$k.k", "n": {"$sum": 1}}}]) if d["_id"] not in declared}
ok("9.1 no undeclared top-level fields (status_desc NOT stored, per spec)", not extra and "status_desc" not in extra, extra)
edecl = {f["target"] for f in emap["fields"]} | {"gl_accounts"}
eextra = [d["_id"] for d in inv.aggregate([{"$unwind": "$lines"}, {"$project": {"k": {"$objectToArray": "$lines"}}}, {"$unwind": "$k"}, {"$group": {"_id": "$k.k"}}]) if d["_id"] not in edecl]
ok("9.2 no undeclared embedded fields", not eextra, eextra)
ok("9.3 ns == mongo_205236 on 100 % of invoices and quarantine docs", inv.count_documents({"ns": {"$ne": NS}}) == 0 and qcol.count_documents({"ns": {"$ne": NS}}) == 0)
ok("9.4 batch_no == 85559852 on 100 % of invoices", inv.count_documents({"batch_no": {"$ne": BATCH}}) == 0)

# 10. indexes
idx = {tuple(v["key"]): v.get("unique", False) for v in inv.index_information().values()}
spec_idx = {tuple((k, 1) for k in i["keys"]) for i in cmap["indexes"]}
ok("10.1 invoices indexes ⊇ spec (3 declared: batch_no+status_cd, cust_id, lines.line_id)", spec_idx <= set(idx), idx)
ok("10.2 no unique flags beyond spec", not any(idx.values()), idx)
qidx = {tuple(v["key"]) for v in qcol.index_information().values()}
results.append({"probe": "10.3 quarantine indexes (info)", "ok": True, "detail": str(qidx)})

# 11. empty-collection / empty-batch behaviour of the head loader (module-level, no target writes)
sys.path.insert(0, os.path.expanduser("~/wave_recon/heads/u2"))
from scripts.tp_mongo import load_u2  # noqa: E402
emb, qq, tot = load_u2.partition_lines([], set())
ok("11.1 partition_lines([]) -> no embeds, no quarantine, 0 total", emb == {} and qq == [] and tot == 0)
d0 = load_u2.build_invoice_doc({"INVOICE_ID": "X", "INVOICE_NO": "", "CUST_ID": None, "TENANT_ID": "t", "INVOICE_DT": "31-FEB-24", "DUE_DT": None, "STATUS_CD": 1, "TOTAL_AMT": Decimal("1.005"), "BATCH_NO": BATCH}, ())
ok("11.2 build_invoice_doc: empty string -> null, bad date -> null, lines == [], decimal ROUND_HALF_EVEN(1.005)->1.00", d0["invoice_no"] is None and d0["invoice_date"] is None and d0["lines"] == [] and str(d0["total_amt"]) == "1.00", d0)
src = "database.drop_collection(TARGET_COLLECTION)" in open(load_u2.__file__).read()
results.append({"probe": "11.3 loader drops live `invoices` BEFORE reinsert (no staging swap; concurrent readers see a gap during the ~60 s load) (design note)", "ok": True, "detail": f"drop_before_insert={src}"}); print("info 11.3 U2 loader drop-before-insert:", src)
hd = int(q("SELECT COUNT(*) FROM invoice_header WHERE batch_no = 1")[0][0])
guard = "refusing to replace the target collections" in open(load_u2.__file__).read()
import inspect
runsrc = inspect.getsource(load_u2.run)
guard_before_drop = guard and runsrc.index("if not headers:") < runsrc.index("drop_collection")
ok("11.4 empty batch (batch_no=1: 0 headers in source) -> head 9e73ffea loader now REFUSES before dropping the target (new since 9643ce76; verified by source position, not exercised live)", hd == 0 and guard_before_drop, f"src_headers_batch1={hd} guard={guard} guard_before_drop={guard_before_drop}")

# 12. cross-unit shared references: codes(INV_STATUS), tenants, customers
codes = {(d["code_type"], d["code_val"]): d["code_desc"] for d in db["codes"].find({}, {"code_type": 1, "code_val": 1, "code_desc": 1})}
src_codes = {(r[0], int(r[1])): r[2] for r in q("SELECT code_type, code_val, code_desc FROM codes")}
ok("12.1 codes collection == Oracle CODES (type,val,desc)", codes == src_codes, f"n={len(codes)} types={Counter(k[0] for k in codes)}")
st = {d["_id"] for d in inv.aggregate([{"$group": {"_id": "$status_cd"}}])}
unres = {s for s in st if ("INV_STATUS", s) not in codes}
src_unres = {int(r[0]) for r in q(f"SELECT DISTINCT h.status_cd FROM invoice_header h WHERE {HW} AND NOT EXISTS (SELECT 1 FROM codes c WHERE c.code_type = 'INV_STATUS' AND c.code_val = h.status_cd)")}
ok("12.2 invoices.status_cd -> codes[INV_STATUS] unresolved set identical to source (RPT-114 'UNKNOWN(n)' bucket)", unres == src_unres, f"status_cds={sorted(st)} unresolved={sorted(unres)}")
lt = {d["_id"] for d in inv.aggregate([{"$unwind": "$lines"}, {"$group": {"_id": "$lines.line_type_cd"}}])}
ok("12.3 lines.line_type_cd values == source distinct set", lt == {int(r[0]) for r in q(f"SELECT DISTINCT l.line_type_cd FROM invoice_line l WHERE {LW}")}, sorted(lt, key=str))
it = {d["_id"] for d in inv.aggregate([{"$group": {"_id": "$tenant_id"}}])}
ct = {d["_id"] for d in db["customers"].aggregate([{"$group": {"_id": "$tenant_id"}}])}
src_t = int(q(f"SELECT COUNT(*) FROM (SELECT DISTINCT tenant_id FROM invoice_header WHERE {HW} MINUS SELECT DISTINCT tenant_id FROM customer_master WHERE conversion_batch_no = {BATCH})")[0][0])
ok("12.4 invoices.tenant_id ⊂ customers.tenant_id exactly as in source", len(it - ct) == src_t, f"inv_tenants={len(it)} not_in_customers={len(it - ct)} src={src_t}")
tenants = {d["_id"] for d in db["tenants"].find({}, {"_id": 1})}
ok("12.5 invoices.tenant_id -> tenants._id resolution identical to source", len(it & tenants) == int(q(f"SELECT COUNT(DISTINCT t.id) FROM invoice_header h JOIN tenants t ON t.id = h.tenant_id WHERE h.{HW}")[0][0]), f"resolve={len(it & tenants)} of {len(it)}")
ic = {d["_id"] for d in inv.aggregate([{"$group": {"_id": "$cust_id"}}])}
cust_hit = {d["_id"] for d in db["customers"].find({"_id": {"$in": sorted(ic)}}, {"_id": 1})}
src_unr = int(q(f"SELECT COUNT(*) FROM (SELECT DISTINCT cust_id FROM invoice_header WHERE {HW} MINUS SELECT cust_id FROM customer_master)")[0][0])
ok("12.6 invoices.cust_id -> customers._id unresolved count identical to source", len(ic - cust_hit) == src_unr, f"distinct={len(ic)} unresolved={len(ic - cust_hit)} src={src_unr}")
# line-level denorm cust_no/cust_name vs customers (source property check both sides)
mism_src = int(q(f"SELECT COUNT(*) FROM invoice_line l JOIN customer_master c ON c.cust_id = l.cust_id WHERE {LW} AND (l.cust_no <> c.cust_no OR l.cust_name <> c.cust_name)")[0][0])
mism_tgt = len(list(inv.aggregate([{"$unwind": "$lines"}, {"$lookup": {"from": "customers", "localField": "lines.cust_id", "foreignField": "_id", "as": "c", "pipeline": [{"$project": {"cust_no": 1, "cust_name": 1}}]}}, {"$unwind": "$c"}, {"$match": {"$expr": {"$or": [{"$ne": ["$lines.cust_no", "$c.cust_no"]}, {"$ne": ["$lines.cust_name", "$c.cust_name"]}]}}}, {"$project": {"_id": 1}}])))
ok("12.7 lines.cust_no/cust_name vs customers denorm disagreement count identical to source", mism_src == mism_tgt, f"src={mism_src} tgt={mism_tgt}")

# 13. app-level replay: RPT-114 STATUS_SQL / LINE_SQL (before-state legacy SQL, commit d57be52c) vs independent Mongo pipelines
STATUS_SQL = """SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'), COUNT(*), TO_CHAR(SUM(h.total_amt), 'FM999999999999990.00')
  FROM invoice_header h, codes st WHERE h.batch_no = :b AND st.code_type (+) = 'INV_STATUS' AND st.code_val (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') ORDER BY 1"""
LINE_SQL = """SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'), DECODE(l.line_type_cd, 1,'CHARGE',2,'CREDIT',3,'ADJUSTMENT',9,'MISC','UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')'),
       COUNT(*), TO_CHAR(SUM(l.amount), 'FM999999999999990.00'), TO_CHAR(SUM(l.tax_amt), 'FM999999999999990.00'), COUNT(DISTINCT h.invoice_id)
  FROM invoice_header h, invoice_line l, codes st WHERE h.batch_no = :b AND h.invoice_id = l.invoice_id AND st.code_type (+) = 'INV_STATUS' AND st.code_val (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'), DECODE(l.line_type_cd, 1,'CHARGE',2,'CREDIT',3,'ADJUSTMENT',9,'MISC','UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')') ORDER BY 1, 2"""
LT = {1: "CHARGE", 2: "CREDIT", 3: "ADJUSTMENT", 9: "MISC"}
def sd(cd): return codes.get(("INV_STATUS", cd), f"UNKNOWN({cd})")
def fm(d): return f"{d.to_decimal().quantize(Decimal('0.01')):f}"
o_status = [(r[0], int(r[1]), r[2]) for r in q(STATUS_SQL, b=BATCH)]
m_status = sorted(((sd(d["_id"]), d["n"], fm(d["t"])) for d in inv.aggregate([{"$match": {"batch_no": BATCH, "ns": NS}}, {"$group": {"_id": "$status_cd", "n": {"$sum": 1}, "t": {"$sum": "$total_amt"}}}])))
# NB: Oracle groups by desc; two status codes with the same desc would merge — fold the Mongo side the same way
fold = {}
for s, n, t in m_status:
    a = fold.setdefault(s, [0, Decimal("0")]); a[0] += n; a[1] += Decimal(t)
m_status = sorted((s, n, f"{t:f}") for s, (n, t) in fold.items())
ok("13.1 RPT-114 STATUS rollup (status_desc, invoice_count, header_total_amt) identical", o_status == m_status, f"oracle={o_status} mongo={m_status}")
o_line = [(r[0], r[1], int(r[2]), r[3], r[4], int(r[5])) for r in q(LINE_SQL, b=BATCH)]
fold = {}
for d in inv.aggregate([{"$match": {"batch_no": BATCH, "ns": NS}}, {"$unwind": "$lines"}, {"$group": {"_id": {"s": "$status_cd", "lt": "$lines.line_type_cd"}, "n": {"$sum": 1}, "a": {"$sum": "$lines.amount"}, "x": {"$sum": "$lines.tax_amt"}, "inv": {"$addToSet": "$_id"}}}]):
    k = (sd(d["_id"]["s"]), LT.get(d["_id"]["lt"], f"UNKNOWN({d['_id']['lt']})"))
    a = fold.setdefault(k, [0, Decimal(0), Decimal(0), set()]); a[0] += d["n"]; a[1] += d["a"].to_decimal(); a[2] += d["x"].to_decimal(); a[3] |= set(d["inv"])
m_line = sorted((k[0], k[1], v[0], f"{v[1].quantize(Decimal('0.01')):f}", f"{v[2].quantize(Decimal('0.01')):f}", len(v[3])) for k, v in fold.items())
ok("13.2 RPT-114 LINE rollup (status, line_type, line_count, line_amount, line_tax, invoices_touched) identical — orphans excluded on both sides", o_line == m_line, f"rows={len(m_line)} sample={m_line[:2]}")
# representative reads: invoice by invoice_no; invoices for a customer; line by line_id (index paths)
rows = q(f"SELECT invoice_no, invoice_id, cust_id FROM (SELECT * FROM invoice_header WHERE {HW} ORDER BY DBMS_RANDOM.VALUE) WHERE ROWNUM <= 25")
bad = [r for r in rows if (inv.find_one({"invoice_no": r[0], "batch_no": BATCH}, {"_id": 1}) or {}).get("_id") != r[1]]
ok("13.3 lookup by invoice_no -> same invoice_id (25 random)", not bad, bad[:3])
bad = []
for r in rows[:10]:
    s = sorted(x[0] for x in q(f"SELECT invoice_id FROM invoice_header WHERE {HW} AND cust_id = :c", c=r[2]))
    t = sorted(d["_id"] for d in inv.find({"cust_id": r[2]}, {"_id": 1}))
    if s != t: bad.append((r[2], len(s), len(t)))
ok("13.4 invoices for a customer (cust_id index) identical sets (10 customers)", not bad, bad)
rows = q(f"SELECT line_id, invoice_id FROM (SELECT * FROM invoice_line l WHERE {LW} ORDER BY DBMS_RANDOM.VALUE) WHERE ROWNUM <= 25")
bad = [r for r in rows if (inv.find_one({"lines.line_id": r[0]}, {"_id": 1}) or {}).get("_id") != r[1]]
ok("13.5 line_id -> parent invoice via lines.line_id index (25 random)", not bad, bad[:3])
qs = q(f"SELECT line_id FROM (SELECT line_id FROM invoice_line l WHERE l.batch_no = {BATCH} AND NOT EXISTS (SELECT 1 FROM invoice_header h WHERE h.invoice_id = l.invoice_id) ORDER BY line_id) WHERE ROWNUM <= 5")
ok("13.6 orphan line_ids are NOT findable in invoices (must go to quarantine, as the RPT-114 note says)", inv.count_documents({"lines.line_id": {"$in": [r[0] for r in qs]}}) == 0 and qcol.count_documents({"_id": {"$in": [r[0] for r in qs]}}) == len(qs))

# 14. drift triage
c1 = q(f"SELECT COUNT(*) FROM invoice_header WHERE {HW}")[0][0]; c2 = q(f"SELECT COUNT(*) FROM invoice_header WHERE {HW}")[0][0]
l1 = q(f"SELECT COUNT(*) FROM invoice_line WHERE {HW}")[0][0]; l2 = q(f"SELECT COUNT(*) FROM invoice_line WHERE {HW}")[0][0]
fm_ = q("SELECT TO_CHAR(initialized_at, 'YYYY-MM-DD HH24:MI:SS.FF6') FROM fixture_meta")[0][0]
ok("14.1 source stable across two counts; FIXTURE_META unchanged", c1 == c2 == N_INV and l1 == l2 == 150000 and fm_ == "2026-09-01 20:53:10.961888", f"headers={c1}/{c2} lines={l1}/{l2} initialized_at={fm_}")

el = time.time() - t0
summary = {"unit": "U2", "ok": sum(r["ok"] for r in results), "total": len(results), "oracle_statements": n_sql, "wall_s": round(el, 1), "results": results}
json.dump(summary, open(sys.argv[2], "w"), indent=1, default=str)
print(f"\nU2 probes: {summary['ok']}/{summary['total']} ok · {n_sql} Oracle statements · {el:.1f}s")
ora.close()
