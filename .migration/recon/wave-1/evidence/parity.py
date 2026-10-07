"""Replay app-level parity queries (fn_invoice_lines, fn_overdue_accounts, fn_entitlement) on source SQL vs target documents. READ-ONLY."""
import json, os, datetime, decimal
import oracledb
from pymongo import MongoClient
from bson.decimal128 import Decimal128
s = json.loads(os.environ['MMP_RT_SRC_DSN'])
ora = oracledb.connect(user=s['user'], password=s['password'], dsn=s['dsn']); cur = ora.cursor()
cur.execute("ALTER SESSION SET CURRENT_SCHEMA = OW_BILLING")
db = MongoClient(os.environ['MONGODB_ATLAS_URI'], serverSelectionTimeoutMS=20000)['mmp_rt_b3_oracle']
def q(sql, **kw): cur.execute(sql, kw); return cur.fetchall()
def d2(v):
    if v is None: return None
    if isinstance(v, Decimal128): v = v.to_decimal()
    return decimal.Decimal(str(v)).quantize(decimal.Decimal('0.01'))
out = {}
# --- fn_invoice_lines(p_invoice_id): SELECT line_no, line_type, description, amount FROM invoice_lines WHERE invoice_id=:1 ORDER BY line_no
res = []
for (inv_id,) in q("SELECT id FROM invoices ORDER BY id"):
    src = [(r[0], r[1], r[2], d2(r[3])) for r in q("SELECT line_no, line_type, description, amount FROM invoice_lines WHERE invoice_id=:p ORDER BY line_no", p=inv_id)]
    doc = db.invoices.find_one({'_id': inv_id}) or {}
    lines = doc.get('lines') or []
    has_line_no = all('lineNo' in l for l in lines)
    tgt_ordered = sorted(lines, key=lambda l: l.get('lineNo')) if has_line_no else lines
    tgt = [(l.get('lineNo'), l.get('lineType'), l.get('description'), d2(l.get('amount'))) for l in tgt_ordered]
    # compare without line_no if the target cannot carry it
    src_nolo = [t[1:] for t in src]; tgt_nolo = [t[1:] for t in tgt]
    res.append({'invoice_id': inv_id, 'source_rows': len(src), 'target_lines': len(tgt), 'target_has_lineNo': has_line_no,
                'exact_match_incl_line_no': src == tgt, 'match_ignoring_line_no_and_order': sorted(src_nolo, key=str) == sorted(tgt_nolo, key=str),
                'match_ignoring_line_no_in_stored_order': src_nolo == tgt_nolo,
                'source': [list(map(str, t)) for t in src], 'target': [list(map(str, t)) for t in tgt]})
out['fn_invoice_lines'] = res
# --- fn_overdue_accounts(p_as_of)
def overdue(as_of):
    src = q("""SELECT i.tenant_id, i.id, i.total, TRUNC(:p) - TRUNC(CAST(i.issued_at AS DATE)), DECODE(t.status_cd, 10,'active',20,'suspended','UNKNOWN')
               FROM invoices i, tenants t WHERE t.id (+) = i.tenant_id AND i.status_cd = 40 AND TO_CHAR(i.issued_at,'YYYYMMDD') < TO_CHAR(:p,'YYYYMMDD')
               ORDER BY i.issued_at, i.id""", p=as_of)
    src = [(r[0], r[1], d2(r[2]), int(r[3]), r[4]) for r in src]
    tgt = []
    for d in db.invoices.find({'statusCd': 40}).sort([('issuedAt', 1), ('_id', 1)]):
        ia = d['issuedAt']
        if ia.strftime('%Y%m%d') >= as_of.strftime('%Y%m%d'): continue
        tst = (d.get('tenant') or {}).get('statusCd'); tenant_status = {10: 'active', 20: 'suspended'}.get(tst, 'UNKNOWN')
        tgt.append((d.get('tenantId'), d['_id'], d2(d.get('total')), (as_of.date() - ia.date()).days, tenant_status))
    # also via tenants collection (reference) instead of copied field
    tgt_ref = []
    for row in tgt:
        t = db.tenants.find_one({'_id': row[0]}); tgt_ref.append(row[:4] + ({10: 'active', 20: 'suspended'}.get((t or {}).get('statusCd'), 'UNKNOWN'),))
    return {'as_of': as_of.isoformat(), 'source_rows': len(src), 'target_rows': len(tgt), 'match_copied_tenant_status': src == tgt, 'match_via_tenants_lookup': src == tgt_ref,
            'source': [list(map(str, r)) for r in src], 'target': [list(map(str, r)) for r in tgt]}
dates = [datetime.datetime(2026, 10, 7), datetime.datetime(2025, 1, 1), datetime.datetime(2099, 12, 31)]
mx = q("SELECT MAX(issued_at), MIN(issued_at) FROM invoices WHERE status_cd=40")[0]
if mx[0]: dates += [mx[0] + datetime.timedelta(days=1), mx[1]]
out['fn_overdue_accounts'] = [overdue(d) for d in dates]
# --- fn_entitlement(p_tenant_id, p_on)
def entitlement(tid, on):
    src = q("""SELECT * FROM (SELECT t.id, p.code, DECODE(p.tier_cd,1,'starter',2,'growth',3,'scale','UNKNOWN'), p.monthly_fee, p.included_units,
                 DECODE(s.status_cd,10,'active',20,'suspended',30,'cancelled','UNKNOWN'), GREATEST(s.starts_on, :p)
               FROM tenants t, subscriptions s, plans p WHERE s.tenant_id = t.id AND p.id (+) = s.plan_id AND t.id = :t AND s.starts_on <= :p
                 AND (s.ends_on IS NULL OR s.ends_on >= :p) ORDER BY s.starts_on DESC) WHERE ROWNUM <= 1""", t=tid, p=on)
    src = [(r[0], r[1], r[2], d2(r[3]), None if r[4] is None else int(r[4]), r[5], r[6]) for r in src]
    tgt = []
    if db.tenants.find_one({'_id': tid}):
        subs = [d for d in db.subscriptions.find({'tenantId': tid, 'startsOn': {'$lte': on}, '$or': [{'endsOn': None}, {'endsOn': {'$exists': False}}, {'endsOn': {'$gte': on}}]}).sort('startsOn', -1).limit(1)]
        for sdoc in subs:
            p = sdoc.get('plan') or {}
            tgt.append((tid, p.get('code'), {1: 'starter', 2: 'growth', 3: 'scale'}.get(p.get('tierCd'), 'UNKNOWN'), d2(p.get('monthlyFee')), p.get('includedUnits'),
                        {10: 'active', 20: 'suspended', 30: 'cancelled'}.get(sdoc.get('statusCd'), 'UNKNOWN'), max(sdoc['startsOn'], on)))
    return {'tenant': tid, 'on': on.isoformat(), 'source': [list(map(str, r)) for r in src], 'target': [list(map(str, r)) for r in tgt], 'match': src == tgt}
tenants = [r[0] for r in q("SELECT id FROM tenants ORDER BY id")]
starts = [r[0] for r in q("SELECT DISTINCT starts_on FROM subscriptions ORDER BY starts_on")]
ons = [datetime.datetime(2026, 10, 7)] + starts[:3] + [starts[-1] + datetime.timedelta(days=1)] if starts else [datetime.datetime(2026, 10, 7)]
ent = [entitlement(t, o) for t in tenants for o in ons]
out['fn_entitlement'] = {'cases': len(ent), 'mismatches': [e for e in ent if not e['match']], 'non_empty_source': sum(1 for e in ent if e['source']),
                         'tie_risk_same_starts_on': q("SELECT COUNT(*) FROM (SELECT tenant_id, starts_on FROM subscriptions GROUP BY tenant_id, starts_on HAVING COUNT(*)>1)")[0][0],
                         'sample': ent[:3]}
json.dump(out, open('/home/ubuntu/verify/parity.json', 'w'), indent=1, default=str)
print('fn_invoice_lines:', [(r['invoice_id'][:8], r['source_rows'], r['target_lines'], r['target_has_lineNo'], r['exact_match_incl_line_no'], r['match_ignoring_line_no_and_order'], r['match_ignoring_line_no_in_stored_order']) for r in res])
print('fn_overdue_accounts:', [(o['as_of'], o['source_rows'], o['target_rows'], o['match_copied_tenant_status'], o['match_via_tenants_lookup']) for o in out['fn_overdue_accounts']])
print('fn_entitlement:', out['fn_entitlement']['cases'], 'non-empty', out['fn_entitlement']['non_empty_source'], 'mismatches', len(out['fn_entitlement']['mismatches']), 'tie_risk', out['fn_entitlement']['tie_risk_same_starts_on'])
for m in out['fn_entitlement']['mismatches'][:5]: print('  MISMATCH', m)
