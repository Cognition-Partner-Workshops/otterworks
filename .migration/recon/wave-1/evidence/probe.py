"""Independent wave-1 probes past the recon gate. READ-ONLY on both sides.
Source: Oracle via MMP_RT_SRC_DSN (ro user). Target: Atlas via MONGODB_ATLAS_URI, db mmp_rt_b3_oracle only."""
import json, os, sys, datetime, decimal
from collections import Counter, defaultdict
import oracledb
from pymongo import MongoClient
from bson.decimal128 import Decimal128

R = '/home/ubuntu/repos/otterworks'
DB = 'mmp_rt_b3_oracle'
spec = json.load(open(f'{R}/.migration/mapping_spec.json'))
cols = {c['collection']: c for c in spec['collections']}
s = json.loads(os.environ['MMP_RT_SRC_DSN'])
ora = oracledb.connect(user=s['user'], password=s['password'], dsn=s['dsn'])
cur = ora.cursor()
cur.execute("ALTER SESSION SET CURRENT_SCHEMA = OW_BILLING")
mc = MongoClient(os.environ['MONGODB_ATLAS_URI'], serverSelectionTimeoutMS=20000)
db = mc[DB]
out = {'probes': {}, 'anomalies': []}
def anomaly(s): out['anomalies'].append(s); print('ANOMALY:', s)
def q(sql, *a):
    cur.execute(sql, a); return cur.fetchall()
def norm(v):
    if isinstance(v, Decimal128): return decimal.Decimal(str(v.to_decimal()))
    if isinstance(v, float): return decimal.Decimal(repr(v))
    if isinstance(v, int) and not isinstance(v, bool): return decimal.Decimal(v)
    if isinstance(v, datetime.datetime): return v.replace(tzinfo=None)
    return v
def dec(v): return None if v is None else decimal.Decimal(str(v)).quantize(decimal.Decimal('0.01'))

existing = set(db.list_collection_names())
# ---------- 1. per-collection counts, keys, null/missing, extra fields ----------
per = {}
for name, c in cols.items():
    rt = c['root_table']
    src_n = q(f"SELECT COUNT(*) FROM {rt}")[0][0]
    exists = name in existing
    tgt_n = db[name].count_documents({}) if exists else 0
    key = c['key']; ktg = key['target'] if isinstance(key['target'], list) else [key['target']]
    dup = []
    if exists and tgt_n:
        grp = {k: f'${k}' for k in ktg}
        dup = list(db[name].aggregate([{'$group': {'_id': grp, 'n': {'$sum': 1}}}, {'$match': {'n': {'$gt': 1}}}, {'$limit': 5}]))
        # key null/missing
        keymiss = db[name].count_documents({'$or': [{k: {'$exists': False}} for k in ktg] + [{k: None} for k in ktg]})
    else: keymiss = 0
    fields = {}
    docs = list(db[name].find({})) if exists else []
    mapped = set(f['target'] for f in c['fields']) | set(ktg) | set(e['array_path'] for e in c.get('embeds', [])) | set(cf['path'] for cf in c.get('copied_fields', []))
    extra = Counter()
    for d in docs:
        for k in d:
            if k not in mapped and k != '_id': extra[k] += 1
    for f in c['fields']:
        t = f['target']; src = f['source']; rules = f['rules']
        if exists and tgt_n:
            missing = sum(1 for d in docs if t not in d); nulls = sum(1 for d in docs if t in d and d[t] is None)
        else: missing = nulls = 0
        if 'empty_string_is_null' in rules:
            snull = q(f"SELECT COUNT(*) FROM {rt} WHERE {src} IS NULL OR TRIM({src}) IS NULL")[0][0]
        else:
            snull = q(f"SELECT COUNT(*) FROM {rt} WHERE {src} IS NULL")[0][0]
        rec = {'target_missing': missing, 'target_null': nulls, 'source_null_or_empty': snull}
        if tgt_n == src_n and src_n and missing + nulls != snull:
            rec['note'] = 'target missing+null != source null'
            # dirty-date rule: unparseable dates become missing + flag? capture
            anomaly(f"{name}.{t}: target missing+null={missing+nulls} vs source null/empty={snull} (rules={rules})")
        fields[t] = rec
    per[name] = {'root_table': rt, 'source_rows': src_n, 'collection_exists': exists, 'target_docs': tgt_n,
                 'duplicate_keys': dup, 'key_null_or_missing': keymiss, 'extra_unmapped_fields': dict(extra), 'fields': fields,
                 'indexes': sorted(db[name].index_information().keys()) if exists else []}
    if src_n != tgt_n: anomaly(f"{name}: source rows {src_n} != target docs {tgt_n}")
    if dup: anomaly(f"{name}: duplicate keys {dup}")
    if keymiss: anomaly(f"{name}: {keymiss} docs with null/missing key")
    if src_n == 0: per[name]['verdict_note'] = 'UNVERIFIED: 0 source rows, 0 target docs; nothing exercised' + ('' if exists else ' (collection never created)')
out['probes']['per_collection'] = per

# ---------- 2. boundary docs: min/max per date/decimal/long field ----------
bounds = {}
for name, c in cols.items():
    if name not in existing or per[name]['target_docs'] == 0: continue
    b = {}
    for f in c['fields']:
        if f['bson_type'] not in ('date', 'decimal', 'long'): continue
        if any(r.startswith('date_string_to_date') for r in f['rules']): continue  # string dates: compared separately
        t, src = f['target'], f['source']
        smin, smax = q(f"SELECT MIN({src}), MAX({src}) FROM {c['root_table']}")[0]
        agg = list(db[name].aggregate([{'$match': {t: {'$ne': None}}}, {'$group': {'_id': None, 'mn': {'$min': f'${t}'}, 'mx': {'$max': f'${t}'}}}]))
        tmin, tmax = (norm(agg[0]['mn']), norm(agg[0]['mx'])) if agg else (None, None)
        smin, smax = norm(smin), norm(smax)
        if f['bson_type'] == 'date':
            ok = (smin is None and tmin is None) or (abs((smin - tmin).total_seconds()) < 0.001 and abs((smax - tmax).total_seconds()) < 0.001)
        elif f['bson_type'] == 'decimal':
            ok = dec(smin) == dec(tmin) and dec(smax) == dec(tmax)
        else:
            ok = smin == tmin and smax == tmax
        b[t] = {'source': [str(smin), str(smax)], 'target': [str(tmin), str(tmax)], 'match': ok}
        if not ok: anomaly(f"{name}.{t}: boundary mismatch source {smin}..{smax} target {tmin}..{tmax}")
    bounds[name] = b
out['probes']['boundaries'] = bounds

# ---------- 3. embed-array lengths vs child-row counts ----------
emb = {}
# invoiceHeader.lines vs INVOICE_LINE (scoped)
src_lines = {r[0]: r[1] for r in q("SELECT invoice_id, COUNT(*) FROM invoice_line GROUP BY invoice_id")}
hdr_ids = set(r[0] for r in q("SELECT invoice_id FROM invoice_header"))
mism = []; tot_emb = 0; emb_line_ids = set(); emb_by_hdr = {}
for d in db.invoiceHeader.find({}, {'lines': 1}):
    n = len(d.get('lines') or []); tot_emb += n; emb_by_hdr[d['_id']] = n
    for l in d.get('lines') or []: emb_line_ids.add(l.get('lineId'))
    if src_lines.get(d['_id'], 0) != n: mism.append((d['_id'], src_lines.get(d['_id'], 0), n))
headers_missing_on_target = hdr_ids - set(emb_by_hdr)
lineless = sum(1 for h in hdr_ids if h not in src_lines)
orph_docs = list(db.invoice_lines_orphaned.find({})) if 'invoice_lines_orphaned' in existing else []
orph_ids = set(d.get('lineId') for d in orph_docs)
src_orph = q("SELECT line_id, invoice_id FROM invoice_line l WHERE NOT EXISTS (SELECT 1 FROM invoice_header h WHERE h.invoice_id=l.invoice_id)")
src_orph_ids = set(r[0] for r in src_orph); src_orph_inv = set(r[1] for r in src_orph)
src_scoped_ids = set(r[0] for r in q("SELECT line_id FROM invoice_line WHERE invoice_id IN (SELECT invoice_id FROM invoice_header)"))
tgt_orph_inv = set(d.get('invoiceId') for d in orph_docs)
orph_resolving_hdr_src = len(tgt_orph_inv & hdr_ids)
orph_resolving_hdr_tgt = db.invoiceHeader.count_documents({'_id': {'$in': list(tgt_orph_inv)}})
out_of_scope_embedded = emb_line_ids - src_scoped_ids
both_sides = emb_line_ids & orph_ids
emb['invoiceHeader_lines'] = {
    'sum_len_lines': tot_emb, 'orphan_sink_docs': len(orph_docs), 'sum_plus_orphans': tot_emb + len(orph_docs),
    'source_invoice_line_rows': q("SELECT COUNT(*) FROM invoice_line")[0][0],
    'source_scoped_rows': len(src_scoped_ids), 'source_orphan_rows': len(src_orph_ids),
    'embedded_lineIds_equal_source_scoped_set': emb_line_ids == src_scoped_ids,
    'orphan_lineIds_equal_source_orphan_set': orph_ids == src_orph_ids,
    'embedded_lineIds_outside_child_where': sorted(out_of_scope_embedded)[:10], 'n_outside_child_where': len(out_of_scope_embedded),
    'lineIds_on_both_sides': len(both_sides),
    'orphan_invoiceIds_distinct': len(tgt_orph_inv), 'orphan_invoiceIds_resolving_to_header_source': orph_resolving_hdr_src,
    'orphan_invoiceIds_resolving_to_header_target': orph_resolving_hdr_tgt,
    'orphan_docs_flag_orphan_true': sum(1 for d in orph_docs if d.get('orphan') is True),
    'orphan_docs_raw_invoiceId_present': sum(1 for d in orph_docs if d.get('invoiceId')),
    'per_header_length_mismatches': mism[:10], 'n_per_header_length_mismatches': len(mism),
    'headers_missing_on_target': len(headers_missing_on_target), 'lineless_headers_source': lineless,
    'lineless_headers_target': sum(1 for n in emb_by_hdr.values() if n == 0),
    'orphan_invoice_no_ghost_pattern_source': q("SELECT COUNT(*) FROM invoice_line WHERE invoice_no LIKE 'MMPRT-GHOST-%'")[0][0],
}
if tot_emb + len(orph_docs) != 1500 or mism or out_of_scope_embedded or both_sides or orph_resolving_hdr_src or orph_resolving_hdr_tgt:
    anomaly(f"invoiceHeader orphan proof failed: {emb['invoiceHeader_lines']}")
# embedded line field parity (full compare of scoped lines)
srcl = {r[0]: r[1:] for r in q("SELECT line_id, invoice_no, cust_id, cust_no, cust_name, tenant_id, line_no, line_type_cd, item_desc, qty, unit_price, amount, tax_amt, invoice_dt, service_period, posted_yn, gl_acct_csv, batch_no, src_system FROM invoice_line WHERE invoice_id IN (SELECT invoice_id FROM invoice_header)")}
bad = 0; ex = []
for d in db.invoiceHeader.find({}, {'lines': 1}):
    for l in d.get('lines') or []:
        r = srcl.get(l['lineId'])
        if r is None: bad += 1; continue
        chk = [(l.get('invoiceNo'), r[0] or None), (l.get('custId'), r[1] or None), (l.get('lineNo'), r[5]), (l.get('lineTypeCd'), r[6]), (l.get('itemDesc'), r[7] or None),
               (dec(norm(l.get('qty'))) if l.get('qty') is not None else None, dec(r[8])), (dec(norm(l.get('amount'))) if l.get('amount') is not None else None, dec(r[10])),
               (l.get('posted'), None if r[14] is None else r[14] == 'Y'), (l.get('batchNo'), r[16])]
        for a, b in chk:
            if a is not None and b is not None and norm(a) != norm(b): bad += 1; ex.append((l['lineId'], a, b)); break
emb['invoiceHeader_lines']['embedded_scalar_mismatches'] = bad; emb['invoiceHeader_lines']['examples'] = ex[:5]
if bad: anomaly(f"invoiceHeader.lines scalar mismatches: {bad} e.g. {ex[:3]}")

# customerMaster.attributes vs ENTITY_ATTR_VALUE
eav_by_ent = Counter(r[0] for r in q("SELECT entity_id FROM entity_attr_value"))
eav_cust = Counter(r[0] for r in q("SELECT entity_id FROM entity_attr_value WHERE entity_type='CUSTOMER'"))
eav_types = dict(Counter(r[0] for r in q("SELECT entity_type FROM entity_attr_value")))
cust_ids = set(r[0] for r in q("SELECT cust_id FROM customer_master"))
eav_nonresolving = q("SELECT COUNT(*) FROM entity_attr_value e WHERE NOT EXISTS (SELECT 1 FROM customer_master c WHERE c.cust_id=e.entity_id)")[0][0]
mism2 = []; tot_attr = 0; attr_keys = Counter(); shapes = Counter()
for d in db.customerMaster.find({}, {'attributes': 1}):
    a = d.get('attributes') or []; tot_attr += len(a)
    for x in a: attr_keys[tuple(sorted(x.keys()))] += 1
    if eav_by_ent.get(d['_id'], 0) != len(a): mism2.append((d['_id'], eav_by_ent.get(d['_id'], 0), eav_cust.get(d['_id'], 0), len(a)))
emb['customerMaster_attributes'] = {'sum_len_attributes': tot_attr, 'source_eav_rows': sum(eav_by_ent.values()), 'source_eav_by_entity_type': eav_types,
    'source_eav_rows_not_resolving_to_customer': eav_nonresolving, 'per_customer_mismatches_(custId,eav_all,eav_CUSTOMER,target)': mism2[:10], 'n_mismatches': len(mism2),
    'attribute_element_shapes': {str(k): v for k, v in attr_keys.items()}}
if mism2: anomaly(f"customerMaster.attributes length mismatches: {len(mism2)} e.g. {mism2[:3]}; EAV rows not resolving to a customer: {eav_nonresolving}")
# invoices.lines vs INVOICE_LINES
il = Counter(r[0] for r in q("SELECT invoice_id FROM invoice_lines"))
mism3 = []; tot3 = 0; line_shapes = Counter()
for d in db.invoices.find({}, {'lines': 1}):
    a = d.get('lines') or []; tot3 += len(a)
    for x in a: line_shapes[tuple(sorted(x.keys()))] += 1
    if il.get(d['_id'], 0) != len(a): mism3.append((d['_id'], il.get(d['_id'], 0), len(a)))
emb['invoices_lines'] = {'sum_len_lines': tot3, 'source_rows': sum(il.values()), 'mismatches': mism3, 'element_shapes': {str(k): v for k, v in line_shapes.items()},
                         'index_lines.lineNo_present': any('lines.lineNo' in str(v.get('key')) for v in db.invoices.index_information().values()),
                         'docs_with_lines.lineNo': db.invoices.count_documents({'lines.lineNo': {'$exists': True}})}
if mism3: anomaly(f"invoices.lines length mismatches {mism3}")
if emb['invoices_lines']['index_lines.lineNo_present'] and emb['invoices_lines']['docs_with_lines.lineNo'] == 0 and tot3:
    anomaly("invoices: index on lines.lineNo exists but no embedded line carries lineNo (INVOICE_LINES.LINE_NO is not mapped); fn_invoice_lines ORDER BY line_no cannot be replayed on the target")
out['probes']['embeds'] = emb

# ---------- 4. dirty-date flags / string dates ----------
dd = {}
for name, c in cols.items():
    if name not in existing or per[name]['target_docs'] == 0: continue
    for f in c['fields']:
        if not any(r.startswith('date_string_to_date') for r in f['rules']): continue
        t, src = f['target'], f['source']
        n_date = db[name].count_documents({t: {'$type': 'date'}}); n_str = db[name].count_documents({t: {'$type': 'string'}})
        n_null = db[name].count_documents({t: None}); n_missing = db[name].count_documents({t: {'$exists': False}})
        flags = Counter()
        for d in db[name].find({}, {}):
            for k in d:
                if k.lower().startswith(t.lower()) and k != t: flags[k] += 1
        s_nonnull = q(f"SELECT COUNT(*) FROM {c['root_table']} WHERE {src} IS NOT NULL")[0][0]
        # source rows not matching the DD-MON-YY shape
        s_bad = q(f"SELECT COUNT(*) FROM {c['root_table']} WHERE {src} IS NOT NULL AND NOT REGEXP_LIKE({src}, '^[0-9]{{2}}-[A-Za-z]{{3}}-[0-9]{{2}}$')")[0][0]
        dd[f'{name}.{t}'] = {'target_date': n_date, 'target_string': n_str, 'target_null': n_null, 'target_missing': n_missing, 'sibling_flag_fields': dict(flags),
                             'source_non_null': s_nonnull, 'source_not_DD-MON-YY_shape': s_bad, 'rule': [r for r in f['rules'] if r.startswith('date_string')][0]}
        if n_date + n_str + n_null + n_missing != per[name]['target_docs'] or n_date != s_nonnull - s_bad:
            anomaly(f"{name}.{t}: date-string disposition: target date={n_date} string={n_str} null={n_null} missing={n_missing}; source non-null={s_nonnull} malformed={s_bad}")
# embedded string dates
for t, src in (('invoiceDt', 'invoice_dt'),):
    n_date = db.invoiceHeader.count_documents({'lines.' + t: {'$type': 'date'}})
    s_bad = q(f"SELECT COUNT(*) FROM invoice_line WHERE invoice_id IN (SELECT invoice_id FROM invoice_header) AND {src} IS NOT NULL AND NOT REGEXP_LIKE({src}, '^[0-9]{{2}}-[A-Za-z]{{3}}-[0-9]{{2}}$')")[0][0]
    el = list(db.invoiceHeader.aggregate([{'$unwind': '$lines'}, {'$group': {'_id': {'$type': '$lines.' + t}, 'n': {'$sum': 1}}}]))
    dd[f'invoiceHeader.lines.{t}'] = {'element_types': {e['_id']: e['n'] for e in el}, 'source_malformed_in_scope': s_bad}
out['probes']['dirty_dates'] = dd

# ---------- 5. codes vs CODES, and code domains ----------
src_codes = {(r[0], r[1]): r[2] for r in q("SELECT code_type, code_val, code_desc FROM codes")}
tgt_codes = {(d.get('codeType'), d.get('codeVal')): d.get('codeDesc') for d in db.codes.find({})}
codes_cmp = {'source_rows': len(src_codes), 'target_docs': len(tgt_codes), 'keys_equal': set(src_codes) == set(tgt_codes),
             'desc_mismatches': [(k, src_codes[k], tgt_codes.get(k)) for k in src_codes if (src_codes[k] or None) != tgt_codes.get(k)],
             'code_types': sorted(set(k[0] for k in src_codes)), 'codeVal_bson_types': dict(Counter(type(k[1]).__name__ for k in tgt_codes))}
if not codes_cmp['keys_equal'] or codes_cmp['desc_mismatches']: anomaly(f"codes mismatch {codes_cmp}")
def domain(ctype): return set(k[1] for k in src_codes if k[0] == ctype)
dom_checks = {}
for coll, fld, ctype in (('tenants', 'statusCd', 'TENANT_STATUS'), ('invoices', 'statusCd', 'INV_STATUS'), ('plans', 'tierCd', 'PLAN_TIER'), ('subscriptions', 'statusCd', 'SUB_STATUS'),
                         ('usageEvents', 'kindCd', 'USAGE_KIND'), ('notifications', 'kindCd', 'NOTIF_KIND'), ('dunningAttempts', 'statusCd', 'DUNNING_STATUS'),
                         ('invoiceHeader', 'statusCd', 'INV_STATUS'), ('customerMaster', 'statusCd', 'CUST_STATUS')):
    dom = domain(ctype); dom_s = set(str(x) for x in dom)
    vals = Counter(str(d.get(fld)) for d in db[coll].find({}, {fld: 1}))
    dom_checks[f'{coll}.{fld}'] = {'codes_type': ctype, 'codes_domain_exists': bool(dom), 'domain': sorted(dom_s), 'target_values': dict(vals), 'outside_domain': sorted(v for v in vals if v not in dom_s and v != 'None')}
out['probes']['codes'] = {'codes_vs_CODES': codes_cmp, 'domains': dom_checks}

# ---------- 6. cross-unit references + copied fields ----------
xr = {}
def refcheck(coll, fld, to, srctab, srccol, totab, tocol):
    tgt_vals = [d[fld] for d in db[coll].find({fld: {'$ne': None}}, {fld: 1}) if fld in d]
    tgt_dangling = len(set(tgt_vals) - set(d['_id'] for d in db[to].find({}, {'_id': 1})))
    src_dangling = q(f"SELECT COUNT(DISTINCT {srccol}) FROM {srctab} a WHERE {srccol} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {totab} b WHERE b.{tocol}=a.{srccol})")[0][0]
    xr[f'{coll}.{fld}->{to}'] = {'target_dangling_distinct': tgt_dangling, 'source_dangling_distinct': src_dangling, 'match': tgt_dangling == src_dangling}
    if tgt_dangling != src_dangling: anomaly(f"xref {coll}.{fld}->{to}: target dangling {tgt_dangling} vs source {src_dangling}")
refcheck('invoiceHeader', 'custId', 'customerMaster', 'invoice_header', 'cust_id', 'customer_master', 'cust_id')
refcheck('invoiceHeader', 'tenantId', 'tenants', 'invoice_header', 'tenant_id', 'tenants', 'id')
refcheck('customerMaster', 'tenantId', 'tenants', 'customer_master', 'tenant_id', 'tenants', 'id')
refcheck('subscriptions', 'planId', 'plans', 'subscriptions', 'plan_id', 'plans', 'id')
refcheck('subscriptions', 'tenantId', 'tenants', 'subscriptions', 'tenant_id', 'tenants', 'id')
refcheck('invoices', 'tenantId', 'tenants', 'invoices', 'tenant_id', 'tenants', 'id')
refcheck('invoices', 'periodId', 'ratingPeriods', 'invoices', 'period_id', 'rating_periods', 'id')
refcheck('dunningAttempts', 'invoiceId', 'invoices', 'dunning_attempts', 'invoice_id', 'invoices', 'id')
refcheck('ratingResults', 'subscriptionId', 'subscriptions', 'rating_results', 'subscription_id', 'subscriptions', 'id')
refcheck('ratingResults', 'periodId', 'ratingPeriods', 'rating_results', 'period_id', 'rating_periods', 'id')
refcheck('usageEvents', 'tenantId', 'tenants', 'usage_events', 'tenant_id', 'tenants', 'id')
refcheck('creditNotes', 'tenantId', 'tenants', 'credit_notes', 'tenant_id', 'tenants', 'id')
refcheck('notifications', 'tenantId', 'tenants', 'notifications', 'tenant_id', 'tenants', 'id')
# copied fields
ten = {d['_id']: d for d in db.tenants.find({})}; pl = {d['_id']: d for d in db.plans.find({})}
bad_t = [(d['_id'], (d.get('tenant') or {}).get('statusCd'), ten.get(d.get('tenantId'), {}).get('statusCd')) for d in db.invoices.find({}) if (d.get('tenant') or {}).get('statusCd') != ten.get(d.get('tenantId'), {}).get('statusCd')]
bad_p = []
for d in db.subscriptions.find({}):
    p = pl.get(d.get('planId'), {}); cp = d.get('plan') or {}
    if (cp.get('code'), cp.get('tierCd'), norm(cp.get('monthlyFee')), cp.get('includedUnits')) != (p.get('code'), p.get('tierCd'), norm(p.get('monthlyFee')), p.get('includedUnits')): bad_p.append(d['_id'])
xr['copied.invoices.tenant.statusCd_vs_tenants'] = {'mismatches': bad_t}
xr['copied.subscriptions.plan_vs_plans'] = {'mismatches': bad_p}
if bad_t or bad_p: anomaly(f"copied-field drift: invoices.tenant {bad_t[:3]} subscriptions.plan {bad_p[:3]}")
out['probes']['cross_unit'] = xr

# ---------- 7. F73: subscriptionsHist.histDt rule vs trigger ----------
ddl = open(f'{R}/services/legacy-billing/db/oracle/schema/01_tables.sql').read()
import re
trg = re.search(r"CREATE OR REPLACE TRIGGER trg_subscriptions_hist.*?/\n", ddl, re.S).group(0)
fmt = re.findall(r"TO_CHAR\(SYSDATE, '([^']+)'\)", trg)
hist_rule = [f['rules'] for f in cols['subscriptionsHist']['fields'] if f['target'] == 'histDt'][0]
hist_col = re.search(r"hist_dt\s+VARCHAR2\((\d+)\)", ddl, re.I)
out['probes']['F73_histDt'] = {'trigger_to_char_formats': fmt, 'mapping_rules': hist_rule, 'hist_dt_column': hist_col.group(0) if hist_col else None,
    'source_rows': per['subscriptionsHist']['source_rows'], 'defect_latent': 'DD-MON-YY HH24:MI:SS' in fmt and 'date_string_to_date' in hist_rule and per['subscriptionsHist']['source_rows'] == 0}

# ---------- 8. F74: fixture-first artifacts ----------
ff = {}
for name in cols:
    p = f'{R}/.migration/recon/{name}/fixture/result.json'
    if os.path.exists(p):
        j = json.load(open(p)); ff[name] = {'present': True, 'mode': j.get('mode'), 'mapping': j.get('mapping_version'), 'status': j.get('status')}
    else: ff[name] = {'present': False}
    lp = f'{R}/.migration/recon/{name}/result.json'
    if os.path.exists(lp):
        j = json.load(open(lp)); ff[name].update({'batch_live_mode': j.get('mode'), 'batch_live_mapping': j.get('mapping_version'), 'batch_live_status': j.get('status')})
out['probes']['F74_fixture_first'] = ff
json.dump(out, open('/home/ubuntu/verify/probes.json', 'w'), indent=1, default=str)
print(json.dumps({k: v for k, v in out['probes'].items() if k not in ('per_collection', 'boundaries')}, indent=1, default=str)[:12000])
print('ANOMALIES:', len(out['anomalies']))
