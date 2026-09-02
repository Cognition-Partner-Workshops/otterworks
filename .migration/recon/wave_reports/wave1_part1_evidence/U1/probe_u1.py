"""Independent adversarial probes for U1 (customers / customers_history / counters + quarantine).
Read-only on both sides. Secrets by NAME (OW_BILLING_FIXTURE_DSN, MONGODB_ATLAS_URI).
One Oracle connection, strictly serial (source-load cap 1)."""
import json, os, re, sys, time
from collections import Counter
from datetime import datetime
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
cust = db["customers"]; hist = db["customers_history"]
spec = json.load(open(sys.argv[1]))
cmap = next(c for c in spec["collections"] if c["collection"] == "customers")
hmap = next(c for c in spec["collections"] if c["collection"] == "customers_history")
results = []; n_sql = 0
def q(sql, **kw):
    global n_sql; n_sql += 1; cur.execute(sql, kw); return cur.fetchall()
def ok(name, cond, detail=""):
    results.append({"probe": name, "ok": bool(cond), "detail": str(detail)[:600]})
    print(("ok   " if cond else "FLAG ") + name + (" — " + str(detail)[:300] if detail else ""))
t0 = time.time()
WHERE = f"conversion_batch_no = {BATCH}"

# 1. null / missing / empty-string distribution per field (all 155 fields)
tgt_null = {}
proj = {f["target"]: {"$cond": [{"$or": [{"$eq": [{"$type": "$" + f["target"]}, "missing"]}, {"$eq": ["$" + f["target"], None]}]}, 1, 0]} for f in cmap["fields"]}
proj_missing = {f["target"] + "__m": {"$cond": [{"$eq": [{"$type": "$" + f["target"]}, "missing"]}, 1, 0]} for f in cmap["fields"]}
proj_empty = {f["target"] + "__e": {"$cond": [{"$eq": ["$" + f["target"], ""]}, 1, 0]} for f in cmap["fields"]}
grp = {"_id": None} | {k: {"$sum": "$" + k} for k in list(proj) + list(proj_missing) + list(proj_empty)}
agg = list(cust.aggregate([{"$project": proj | proj_missing | proj_empty}, {"$group": grp}]))[0]
cols = [f["source"] for f in cmap["fields"]]
src_null = {}
for i in range(0, len(cols), 40):
    chunk = cols[i:i + 40]
    row = q(f"SELECT {', '.join(f'SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END)' for c in chunk)} FROM customer_master WHERE {WHERE}")[0]
    src_null.update(dict(zip(chunk, [int(v) for v in row])))
bad = [(f["source"], src_null[f["source"]], agg[f["target"]]) for f in cmap["fields"] if src_null[f["source"]] != agg[f["target"]]]
ok("1.1 null+missing per field == source NULL count (155 fields)", not bad, bad[:10] or f"nullable fields with NULLs: {sum(1 for v in src_null.values() if v)}")
missing_fields = [f["target"] for f in cmap["fields"] if agg[f["target"] + "__m"]]
ok("1.2 explicit_null policy: no MISSING fields (tolerance v1 target_policy=explicit_null)", not missing_fields, missing_fields[:10])
empty_fields = [f["target"] for f in cmap["fields"] if agg[f["target"] + "__e"]]
ok("1.3 no empty strings in target", not empty_fields, empty_fields[:10])
top_null = sorted(((v, k) for k, v in src_null.items() if v), reverse=True)[:8]
results.append({"probe": "1.4 top null-rate fields (info)", "ok": True, "detail": str(top_null)})

# 2. BSON type audit per field exactly per spec
want = {"string": "string", "int": "int", "long": "long", "decimal": "decimal", "date": "date"}
tproj = {f["target"]: {"$type": "$" + f["target"]} for f in cmap["fields"]}
type_bad = []
for f in cmap["fields"]:
    types = {d["_id"]: d["n"] for d in cust.aggregate([{"$group": {"_id": {"$type": "$" + f["target"]}, "n": {"$sum": 1}}}])}
    allowed = {want[f["bson_type"]], "null"}
    if set(types) - allowed: type_bad.append((f["target"], types))
ok("2.1 BSON type per field == spec (or null)", not type_bad, type_bad[:8])
etype_bad = []
for f in cmap["embeds"][0]["fields"]:
    types = {d["_id"]: d["n"] for d in cust.aggregate([{"$unwind": "$attributes"}, {"$group": {"_id": {"$type": "$attributes." + f["target"]}, "n": {"$sum": 1}}}])}
    if set(types) - {want[f["bson_type"]], "null"}: etype_bad.append((f["target"], types))
ok("2.2 embed element BSON types == spec", not etype_bad, etype_bad)
key_types = {d["_id"]: d["n"] for d in cust.aggregate([{"$group": {"_id": {"$type": "$_id"}, "n": {"$sum": 1}}}])}
ok("2.3 _id is string (CUST_ID VARCHAR2) on all docs", key_types == {"string": 25000}, key_types)

# 3. duplicate keys / uniqueness
ok("3.1 _id == cust_id on all docs", cust.count_documents({"$expr": {"$ne": ["$_id", "$cust_id"]}}) == 0)
dup_tc = list(cust.aggregate([{"$group": {"_id": {"t": "$tenant_id", "c": "$cust_no"}, "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$limit": 3}]))
src_dup_tc = q(f"SELECT COUNT(*) FROM (SELECT tenant_id, cust_no FROM customer_master WHERE {WHERE} GROUP BY tenant_id, cust_no HAVING COUNT(*) > 1)")[0][0]
ok("3.2 (tenant_id,cust_no) duplicates: target 0, source 0 (loader's UNIQUE index has no source UQ constraint — design note)", not dup_tc and src_dup_tc == 0, f"src_dup_groups={src_dup_tc}")
src_dup_cn = q(f"SELECT COUNT(*) FROM (SELECT cust_no FROM customer_master WHERE {WHERE} GROUP BY cust_no HAVING COUNT(*) > 1)")[0][0]
tgt_dup_cn = len(list(cust.aggregate([{"$group": {"_id": "$cust_no", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}])))
results.append({"probe": "3.3 cust_no duplicate groups (info)", "ok": True, "detail": f"source={src_dup_cn} target_has_dups={bool(tgt_dup_cn)}"})
eav_dup = list(cust.aggregate([{"$unwind": "$attributes"}, {"$group": {"_id": "$attributes.eav_id", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}]))
ok("3.4 eav_id unique across all embedded attributes", not eav_dup)
seq_dup = list(cust.aggregate([{"$group": {"_id": "$cust_seq_no", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}, {"$count": "n"}]))
src_seq_dup = q(f"SELECT COUNT(*) FROM (SELECT cust_seq_no FROM customer_master WHERE {WHERE} GROUP BY cust_seq_no HAVING COUNT(*) > 1)")[0][0]
ok("3.5 cust_seq_no duplicates equal (source vs target)", bool(seq_dup) == bool(src_seq_dup), f"src_groups={src_seq_dup}")

# 4. min/max boundary docs — full-field compare for the rows at MIN/MAX of every numeric/date field + key + string LENGTH extremes
def to_cmp_src(f, v):
    if v is None: return None
    bt = f["bson_type"]
    if bt == "string": return (str(v).rstrip(" ") if "rstrip_spaces" in f["rules"] else str(v)) or None
    if bt in ("int", "long"): return int(v)
    if bt == "decimal":
        mt = re.search(r"NUMBER\(\d+,(\d+)\)", f["source_type"]); sc = int(mt.group(1)) if mt else 2
        return Decimal(str(v)).quantize(Decimal(1).scaleb(-sc))
    if bt == "date": return v.replace(microsecond=(v.microsecond // 1000) * 1000)
def to_cmp_tgt(f, v):
    if v is None: return None
    if isinstance(v, Decimal128): return v.to_decimal()
    if isinstance(v, Int64): return int(v)
    return v
def compare_keys(keys, label):
    if not keys: return ok(label, True, "no keys")
    keys = sorted(set(keys))
    diffs = []; n = 0
    for i in range(0, len(keys), 500):
        chunk = keys[i:i + 500]
        binds = {f"k{j}": k for j, k in enumerate(chunk)}
        rows = q(f"SELECT {', '.join(cols)} FROM customer_master WHERE cust_id IN ({', '.join(':' + b for b in binds)})", **binds)
        docs = {d["_id"]: d for d in cust.find({"_id": {"$in": chunk}})}
        for r in rows:
            n += 1; row = dict(zip(cols, r)); d = docs.get(row["CUST_ID"])
            if d is None: diffs.append((row["CUST_ID"], "missing")); continue
            for f in cmap["fields"]:
                a, b = to_cmp_src(f, row[f["source"]]), to_cmp_tgt(f, d.get(f["target"]))
                if a != b: diffs.append((row["CUST_ID"], f["source"], a, b))
    ok(label, not diffs, diffs[:5] or f"{n} rows × 155 fields equal")
bkeys = []
for f in cmap["fields"]:
    if f["bson_type"] in ("int", "long", "decimal", "date"):
        r = q(f"SELECT MIN(cust_id) KEEP (DENSE_RANK FIRST ORDER BY {f['source']}), MIN(cust_id) KEEP (DENSE_RANK LAST ORDER BY {f['source']}) FROM customer_master WHERE {WHERE} AND {f['source']} IS NOT NULL")[0]
        bkeys += [k for k in r if k]
for c in ("CUST_ID", "CUST_NAME", "CONTACT_NOTES", "EMAIL_1", "RELATED_ACCT_IDS", "ZIP", "PHONE1"):
    r = q(f"SELECT MIN(cust_id) KEEP (DENSE_RANK FIRST ORDER BY LENGTH({c})), MIN(cust_id) KEEP (DENSE_RANK LAST ORDER BY LENGTH({c})), MIN(cust_id), MAX(cust_id) FROM customer_master WHERE {WHERE} AND {c} IS NOT NULL")[0]
    bkeys += [k for k in r if k]
compare_keys(bkeys, f"4.1 boundary docs (MIN/MAX of every numeric/date field + LENGTH extremes): {len(set(bkeys))} keys, full 155-field compare")
# 4.2 decimal text equality on money fields for boundary docs + random sample (float-free)
money = [f for f in cmap["fields"] if f["bson_type"] == "decimal"]
sample = [d["_id"] for d in cust.aggregate([{"$sample": {"size": 300}}, {"$project": {"_id": 1}}])]
binds = {f"k{j}": k for j, k in enumerate(sample)}
rows = q(f"SELECT cust_id, {', '.join('TO_CHAR(' + f['source'] + ')' for f in money)} FROM customer_master WHERE cust_id IN ({', '.join(':' + b for b in binds)})", **binds)
docs = {d["_id"]: d for d in cust.find({"_id": {"$in": sample}}, {f["target"]: 1 for f in money})}
mdiff = []
for r in rows:
    d = docs[r[0]]
    for f, sv in zip(money, r[1:]):
        tv = d.get(f["target"]); tv = None if tv is None else tv.to_decimal()
        sd = None if sv is None else Decimal(sv)
        if (sd is None) != (tv is None) or (sd is not None and sd.compare(tv) != 0): mdiff.append((r[0], f["source"], sv, str(tv)))
ok("4.2 money fields: Oracle TO_CHAR text == Decimal128 (300 random docs × 16 decimal fields, no float path)", not mdiff, mdiff[:5])

# 5. aggregate-only fields at doc level: SUM/COUNT per tenant for cur_bal_amt & past_due_amt (partitioned aggregates)
src = {r[0]: (Decimal(r[1]), Decimal(r[2]), int(r[3])) for r in q(f"SELECT tenant_id, TO_CHAR(SUM(cur_bal_amt)), TO_CHAR(SUM(past_due_amt)), COUNT(*) FROM customer_master WHERE {WHERE} GROUP BY tenant_id")}
tgt = {d["_id"]: (d["a"].to_decimal(), d["b"].to_decimal(), d["n"]) for d in cust.aggregate([{"$group": {"_id": "$tenant_id", "a": {"$sum": "$cur_bal_amt"}, "b": {"$sum": "$past_due_amt"}, "n": {"$sum": 1}}}])}
pd = [(k, src.get(k), tgt.get(k)) for k in set(src) | set(tgt) if src.get(k) is None or tgt.get(k) is None or src[k][2] != tgt[k][2] or src[k][0].compare(tgt[k][0]) != 0 or src[k][1].compare(tgt[k][1]) != 0]
ok(f"5.1 per-tenant SUM(cur_bal_amt), SUM(past_due_amt), COUNT over {len(src)} tenants equal", not pd, pd[:3])
src = Counter({r[0]: int(r[1]) for r in q(f"SELECT status_cd, COUNT(*) FROM customer_master WHERE {WHERE} GROUP BY status_cd")})
tgt = Counter({d["_id"]: d["n"] for d in cust.aggregate([{"$group": {"_id": "$status_cd", "n": {"$sum": 1}}}])})
ok("5.2 status_cd distribution equal", src == tgt, dict(tgt))
src = Counter({(r[0] or None): int(r[1]) for r in q(f"SELECT vip_yn, COUNT(*) FROM customer_master WHERE {WHERE} GROUP BY vip_yn")})
tgt = Counter({d["_id"]: d["n"] for d in cust.aggregate([{"$group": {"_id": "$vip_yn", "n": {"$sum": 1}}}])})
ok("5.3 vip_yn distribution equal (CHAR(1) incl. NULL)", src == tgt, dict(tgt))

# 6. embed-array length distribution vs child rows
src_len = Counter(int(r[1]) for r in q(f"SELECT c.cust_id, COUNT(e.eav_id) FROM customer_master c LEFT JOIN entity_attr_value e ON e.entity_type = 'CUSTOMER' AND e.entity_id = c.cust_id WHERE c.{WHERE} GROUP BY c.cust_id"))
tgt_len = Counter(d["_id"] for d in cust.aggregate([{"$project": {"n": {"$size": {"$ifNull": ["$attributes", []]}}}}, {"$group": {"_id": "$n"}}]))
tgt_len = Counter({d["_id"]: d["n"] for d in cust.aggregate([{"$project": {"n": {"$size": {"$ifNull": ["$attributes", []]}}}}, {"$group": {"_id": "$n", "n": {"$sum": 1}}}])})
ok("6.1 attributes[] length distribution == per-customer child-row histogram", src_len == tgt_len, dict(sorted(tgt_len.items())))
ok("6.2 attributes[] present as an array on every doc (incl. 0-length)", cust.count_documents({"attributes": {"$type": "array"}}) == 25000)
ok("6.3 every element's entity_id == parent _id and entity_type == 'CUSTOMER'", cust.count_documents({"$expr": {"$gt": [{"$size": {"$filter": {"input": "$attributes", "as": "a", "cond": {"$or": [{"$ne": ["$$a.entity_id", "$_id"]}, {"$ne": ["$$a.entity_type", "CUSTOMER"]}]}}}}, 0]}}) == 0)
orph = q("SELECT COUNT(*) FROM entity_attr_value e WHERE e.entity_type = 'CUSTOMER' AND NOT EXISTS (SELECT 1 FROM customer_master c WHERE c.cust_id = e.entity_id)")[0][0]
other = q("SELECT entity_type, COUNT(*) FROM entity_attr_value GROUP BY entity_type")
ok("6.4 source orphan EAV rows (CUSTOMER, no parent) == 0; other entity types out of scope", orph == 0, f"orphans={orph} entity_types={other}")
ok("6.5 elements sorted by eav_id inside each doc", cust.count_documents({"$expr": {"$ne": ["$attributes.eav_id", {"$sortArray": {"input": "$attributes.eav_id", "sortBy": 1}}]}}) == 0)
src_an = Counter({r[0]: int(r[1]) for r in q("SELECT attr_name, COUNT(*) FROM entity_attr_value WHERE entity_type='CUSTOMER' GROUP BY attr_name")})
tgt_an = Counter({d["_id"]: d["n"] for d in cust.aggregate([{"$unwind": "$attributes"}, {"$group": {"_id": "$attributes.attr_name", "n": {"$sum": 1}}}])})
ok("6.6 attr_name distribution equal", src_an == tgt_an, dict(tgt_an))

# 7. quarantine classes as SETS against expected counts (manifest: dirty_dates 50, malformed_csv_lists 31)
src_dirty = {r[0] for r in q(f"SELECT cust_id FROM customer_master WHERE {WHERE} AND signup_dt IS NOT NULL AND TO_DATE(signup_dt DEFAULT NULL ON CONVERSION ERROR, 'DD-MON-RR', 'NLS_DATE_LANGUAGE=AMERICAN') IS NULL")}
qd = list(qdb["dirty_signup_dt"].find({}))
tgt_dirty = {d["cust_id"] for d in qd}
ok(f"7.1 dirty_signup_dt SET == Oracle TO_DATE(... DEFAULT NULL ON CONVERSION ERROR) set; expected 50", src_dirty == tgt_dirty and len(tgt_dirty) == 50, f"src={len(src_dirty)} tgt={len(tgt_dirty)} symdiff={sorted(src_dirty ^ tgt_dirty)[:5]}")
ok("7.2 dirty rows still migrated verbatim with signup_date null", cust.count_documents({"_id": {"$in": sorted(tgt_dirty)}, "signup_date": None, "signup_dt": {"$ne": None}}) == len(tgt_dirty))
ok("7.3 non-quarantined rows with signup_dt have a parsed signup_date", cust.count_documents({"_id": {"$nin": sorted(tgt_dirty)}, "signup_dt": {"$ne": None}, "signup_date": None}) == 0)
TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")
def bad_csv(v):
    if v is None: return None
    toks = [t.strip() for t in v.split(",")]
    if any(t == "" for t in toks): return "empty_token"
    if any(not TOKEN.match(t) for t in toks): return "invalid_token"
    return None
src_bad = set()
for col in ("RELATED_ACCT_IDS", "CHILD_ACCT_IDS", "PROMO_CODES_CSV"):
    for r in q(f"SELECT cust_id, {col} FROM customer_master WHERE {WHERE} AND {col} IS NOT NULL"):
        if bad_csv(r[1]): src_bad.add((r[0], col, bad_csv(r[1])))
qb = list(qdb["bad_csv_list"].find({}))
tgt_bad = {(d["cust_id"], d["source_column"], d["reason"]) for d in qb}
ok("7.4 bad_csv_list SET (cust_id, column, reason) == independent re-derivation; expected 31 on RELATED_ACCT_IDS", src_bad == tgt_bad and len(tgt_bad) == 31 and all(c == "RELATED_ACCT_IDS" for _, c, _ in tgt_bad), f"src={len(src_bad)} tgt={len(tgt_bad)} cols={Counter(c for _, c, _ in tgt_bad)} reasons={Counter(r for _, _, r in tgt_bad)}")
ok("7.5 every quarantine record carries ns + batch_no + verbatim value", all(d.get("ns") == NS and d.get("batch_no") == BATCH and "value" in d for d in qd + qb))
ok("7.6 quarantine ceiling 0.5 %: (50+31)/25000", (len(qd) + len(qb)) / 25000 * 100 <= 0.5, f"{(len(qd)+len(qb))/250:.3f} %")
ok("7.7 quarantine db holds only the declared U1 classes for U1 (no undeclared U1 class)", {c for c in qdb.list_collection_names() if c not in ("invoice_feed_orphan_lines", "orphan_document_snapshots")} == {"dirty_signup_dt", "bad_csv_list"}, qdb.list_collection_names())

# 8. derived (ungraded) twins: internal consistency with the verbatim columns (target-only scans)
pipe_related = {"$expr": {"$and": [{"$ne": ["$related_acct_ids", None]}, {"$ne": ["$related_accounts", None]}, {"$ne": ["$related_accounts", {"$map": {"input": {"$split": ["$related_acct_ids", ","]}, "as": "t", "in": {"$trim": {"input": "$$t"}}}}]}]}}
ok("8.1 related_accounts == split(related_acct_ids) wherever not quarantined", cust.count_documents(pipe_related) == 0)
ok("8.2 quarantined bad_csv rows have related_accounts null and verbatim kept", cust.count_documents({"_id": {"$in": sorted({c for c, _, _ in tgt_bad})}, "related_accounts": None, "related_acct_ids": {"$ne": None}}) == len({c for c, _, _ in tgt_bad}))
ok("8.3 null CSV column -> [] (loader contract)", cust.count_documents({"related_acct_ids": None, "related_accounts": {"$ne": []}}) == 0)
ok("8.4 addresses.billing.lines == [addr_line_1..6]", cust.count_documents({"$expr": {"$ne": ["$addresses.billing.lines", ["$addr_line_1", "$addr_line_2", "$addr_line_3", "$addr_line_4", "$addr_line_5", "$addr_line_6"]]}}) == 0)
ok("8.5 phones[] == non-null phone1..4 with type_cd", cust.count_documents({"$expr": {"$ne": ["$phones", {"$filter": {"input": [{"number": "$phone1", "type_cd": "$phone1_type_cd"}, {"number": "$phone2", "type_cd": "$phone2_type_cd"}, {"number": "$phone3", "type_cd": "$phone3_type_cd"}, {"number": "$phone4", "type_cd": "$phone4_type_cd"}], "as": "p", "cond": {"$ne": ["$$p.number", None]}}}]}}) == 0)
# signup_date parse cross-check against Oracle for a sample of parseable rows
rows = q(f"SELECT cust_id, signup_dt, TO_CHAR(TO_DATE(signup_dt, 'DD-MON-YY', 'NLS_DATE_LANGUAGE=AMERICAN'), 'YYYY-MM-DD') FROM (SELECT cust_id, signup_dt FROM customer_master WHERE {WHERE} AND signup_dt IS NOT NULL AND TO_DATE(signup_dt DEFAULT NULL ON CONVERSION ERROR, 'DD-MON-YY', 'NLS_DATE_LANGUAGE=AMERICAN') IS NOT NULL ORDER BY DBMS_RANDOM.VALUE) WHERE ROWNUM <= 400")
docs = {d["_id"]: d for d in cust.find({"_id": {"$in": [r[0] for r in rows]}}, {"signup_date": 1})}
dd = [(r[0], r[1], r[2], docs[r[0]].get("signup_date")) for r in rows if docs[r[0]].get("signup_date") is None or docs[r[0]]["signup_date"].strftime("%Y-%m-%d") != r[2]]
ok("8.6 signup_date == Oracle TO_DATE(signup_dt,'DD-MON-YY') on 400 random parseable rows (century pivot check)", not dd, dd[:5])
ok("8.7 mailing.zip4/country_cd: no MAIL_ZIP4/MAIL_COUNTRY_CD column in source -> loader emits null (documented gap, not a diff)", cust.count_documents({"addresses.mailing.zip4": {"$ne": None}}) == 0)

# 9. field-set audit
declared = {f["target"] for f in cmap["fields"]} | {"_id", "ns", "attributes"} | {d["target"] for d in cmap["derived_ungraded"]}
extra = Counter()
for d in cust.aggregate([{"$project": {"k": {"$objectToArray": "$$ROOT"}}}, {"$unwind": "$k"}, {"$group": {"_id": "$k.k", "n": {"$sum": 1}}}]):
    if d["_id"] not in declared: extra[d["_id"]] = d["n"]
ok("9.1 no undeclared top-level fields", not extra, dict(extra))
edecl = {f["target"] for f in cmap["embeds"][0]["fields"]}
eextra = [d["_id"] for d in cust.aggregate([{"$unwind": "$attributes"}, {"$project": {"k": {"$objectToArray": "$attributes"}}}, {"$unwind": "$k"}, {"$group": {"_id": "$k.k"}}]) if d["_id"] not in edecl]
ok("9.2 no undeclared embedded element fields", not eextra, eextra)
ok("9.3 ns == mongo_205236 on 100 % of customers / customers_history / counters", cust.count_documents({"ns": {"$ne": NS}}) == 0 and hist.count_documents({"ns": {"$ne": NS}}) == 0 and db["counters"].count_documents({"ns": {"$ne": NS}}) == 0)

# 10. indexes vs spec
idx = {tuple(v["key"]): v.get("unique", False) for k, v in cust.index_information().items()}
spec_idx = {tuple((k, 1) for k in i["keys"]) for i in cmap["indexes"]}
ok("10.1 customers indexes ⊇ spec (3 declared)", spec_idx <= set(idx), f"target={idx}")
ok("10.2 customers index UNIQUE flags: spec declares none; loader marks (tenant_id,cust_no) UNIQUE — beyond spec, source has no UQ (design note, not a grading issue while data is unique)", idx.get((("tenant_id", 1), ("cust_no", 1))) is True, idx)
hidx = {tuple(v["key"]) for v in hist.index_information().values()}
ok("10.3 customers_history indexes: spec declares []; loader adds (cust_id,hist_dt) for the write path (beyond spec, harmless)", hidx == {(("_id", 1),), (("cust_id", 1), ("hist_dt", 1))}, hidx)

# 11. empty-collection behaviour
ok("11.1 customers_history: 0 source rows -> collection exists, 0 docs, indexes present", "customers_history" in db.list_collection_names() and hist.count_documents({}) == 0 and len(hidx) == 2)
hist_src = q("SELECT COUNT(*) FROM customer_master_hist")[0][0]
ok("11.2 CUSTOMER_MASTER_HIST source rows == 0 (twice)", hist_src == 0 and q("SELECT COUNT(*) FROM customer_master_hist")[0][0] == 0)
# empty-batch preflight of the head loader (imports the module; no target writes happen because build_documents raises first)
sys.path.insert(0, os.path.expanduser("~/wave_recon/heads/u1"))
from scripts.tp_mongo import load_u1  # noqa: E402
try:
    load_u1.build_documents(load_u1.load_mapping(os.path.expanduser("~/wave_recon/heads/u1/.migration/03_mapping_spec.json") and __import__("pathlib").Path(os.path.expanduser("~/wave_recon/heads/u1/.migration/03_mapping_spec.json"))), {"customers": [], "attributes": [], "history": [], "sequences": []}, 1)
    ok("11.3 loader refuses an empty root batch (no drop of the good copy)", False, "no exception")
except RuntimeError as e:
    ok("11.3 loader refuses an empty root batch (no drop of the good copy)", "refusing" in str(e), str(e)[:120])

# 12. counters vs USER_SEQUENCES
seqs = {r[0]: int(r[1]) for r in q("SELECT sequence_name, last_number FROM user_sequences WHERE sequence_name IN ('SEQ_CUSTOMER_MASTER','SEQ_CUSTOMER_MASTER_HIST','SEQ_ENTITY_ATTR_VALUE')")}
cnt = {d["source_sequence"]: int(d["seq"]) for d in db["counters"].find({})}
maxseq = int(q(f"SELECT MAX(cust_seq_no) FROM customer_master")[0][0]); maxeav = int(q("SELECT MAX(eav_id) FROM entity_attr_value")[0][0])
ok("12.1 counters == USER_SEQUENCES.LAST_NUMBER (3 sequences)", seqs == cnt, f"{cnt}")
ok("12.2 counters >= MAX(cust_seq_no) / MAX(eav_id) so the write path cannot collide", cnt["SEQ_CUSTOMER_MASTER"] >= maxseq and cnt["SEQ_ENTITY_ATTR_VALUE"] >= maxeav, f"max_seq={maxseq} max_eav={maxeav}")

# 13. cross-unit shared references
tenants = {d["_id"] for d in db["tenants"].find({}, {"_id": 1})}
ct = {d["_id"] for d in cust.aggregate([{"$group": {"_id": "$tenant_id"}}])}
src_res = q("SELECT COUNT(DISTINCT c.tenant_id), COUNT(DISTINCT t.id) FROM customer_master c LEFT JOIN tenants t ON t.id = c.tenant_id")[0]
ok("13.1 customers.tenant_id -> tenants._id resolution identical to source (0 of 50 resolve in BOTH; source property, wave-0 note)", len(ct & tenants) == int(src_res[1]) and len(ct) == int(src_res[0]), f"distinct={len(ct)} resolve_target={len(ct & tenants)} resolve_source={src_res[1]}")
codes = {(d["code_type"], d["code_val"]) for d in db["codes"].find({}, {"code_type": 1, "code_val": 1})}
st = {d["_id"] for d in cust.aggregate([{"$group": {"_id": "$status_cd"}}])}
ok("13.2 customers.status_cd ⊂ codes[CUST_STATUS]", all(("CUST_STATUS", s) in codes for s in st), sorted(st))
inv_c = {d["_id"] for d in db["invoices"].aggregate([{"$group": {"_id": "$cust_id"}}])}
src_inv = q(f"SELECT COUNT(DISTINCT h.cust_id), SUM(CASE WHEN c.cust_id IS NULL THEN 1 ELSE 0 END) FROM (SELECT DISTINCT cust_id FROM invoice_header WHERE batch_no = {BATCH}) h LEFT JOIN customer_master c ON c.cust_id = h.cust_id")[0]
ok("13.3 invoices.cust_id -> customers._id resolution equals source (INVOICE_HEADER.CUST_ID -> CUSTOMER_MASTER)", len(inv_c - {d["_id"] for d in cust.find({"_id": {"$in": sorted(inv_c)}}, {"_id": 1})}) == int(src_inv[1]), f"distinct_inv_cust={len(inv_c)} unresolved_src={src_inv[1]}")

# 14. app-level replay: RPT-114 BALANCES_SQL (services/legacy-billing/app/reports.py) vs independent pipeline
row = q(f"SELECT COUNT(*), TO_CHAR(SUM(cur_bal_amt), 'FM999999999999990.00'), TO_CHAR(SUM(past_due_amt), 'FM999999999999990.00') FROM customer_master WHERE conversion_batch_no = :b", b=BATCH)[0]
agg = list(cust.aggregate([{"$match": {"conversion_batch_no": BATCH, "ns": NS}}, {"$group": {"_id": None, "n": {"$sum": 1}, "cur": {"$sum": "$cur_bal_amt"}, "pd": {"$sum": "$past_due_amt"}}}]))[0]
def fm(d): d = d.to_decimal().quantize(Decimal("0.01")); return f"{d:f}"
tgt_row = (agg["n"], fm(agg["cur"]), fm(agg["pd"]))
ok("14.1 RPT-114 BALANCES (customer_count, current_balance_total, past_due_total) identical", (int(row[0]), row[1], row[2]) == tgt_row, f"oracle={row} mongo={tgt_row}")
# lookup by (tenant_id, cust_no) and by cust_name_upper prefix — representative app reads
rows = q(f"SELECT tenant_id, cust_no, cust_id FROM (SELECT tenant_id, cust_no, cust_id FROM customer_master WHERE {WHERE} ORDER BY DBMS_RANDOM.VALUE) WHERE ROWNUM <= 25")
bad = [r for r in rows if (cust.find_one({"tenant_id": r[0], "cust_no": r[1]}, {"_id": 1}) or {}).get("_id") != r[2]]
ok("14.2 lookup by (tenant_id, cust_no) -> same cust_id, 25 random", not bad, bad[:3])
pref = q(f"SELECT SUBSTR(cust_name_upper, 1, 4) FROM customer_master WHERE {WHERE} AND ROWNUM = 1")[0][0]
s_ids = sorted(r[0] for r in q(f"SELECT cust_id FROM customer_master WHERE {WHERE} AND cust_name_upper LIKE :p", p=pref + "%"))
t_ids = sorted(d["_id"] for d in cust.find({"cust_name_upper": {"$regex": "^" + re.escape(pref)}}, {"_id": 1}))
ok(f"14.3 cust_name_upper prefix search '{pref}%' identical result set", s_ids == t_ids, f"n={len(t_ids)}")
ok("14.4 cust_name_upper == UPPER(cust_name) on all docs (TRG_CUSTOMER_MASTER_SEQ invariant carried)", cust.count_documents({"$expr": {"$ne": ["$cust_name_upper", {"$toUpper": "$cust_name"}]}}) == 0)

# 15. drift triage: source counts twice + FIXTURE_META
c1 = q(f"SELECT COUNT(*) FROM customer_master WHERE {WHERE}")[0][0]; c2 = q(f"SELECT COUNT(*) FROM customer_master WHERE {WHERE}")[0][0]
e1 = q("SELECT COUNT(*) FROM entity_attr_value WHERE entity_type='CUSTOMER'")[0][0]
fm_ = q("SELECT TO_CHAR(initialized_at, 'YYYY-MM-DD HH24:MI:SS.FF6') FROM fixture_meta")[0][0]
ok("15.1 source stable across two counts; FIXTURE_META unchanged", c1 == c2 == 25000 and e1 == 8333 and fm_ == "2026-09-01 20:53:10.961888", f"{c1}/{c2}/{e1} initialized_at={fm_}")

el = time.time() - t0
summary = {"unit": "U1", "ok": sum(r["ok"] for r in results), "total": len(results), "oracle_statements": n_sql, "wall_s": round(el, 1), "results": results}
json.dump(summary, open(sys.argv[2], "w"), indent=1, default=str)
print(f"\nU1 probes: {summary['ok']}/{summary['total']} ok · {n_sql} Oracle statements · {el:.1f}s")
ora.close()
