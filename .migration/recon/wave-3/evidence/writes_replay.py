"""Own replay of the wave-3 write paths that recon cannot grade (runtime writes, not loaded rows):
invoices.dunningAttempts through the invoicing owner API (append_dunning_attempt), the
tenants.creditNotes drawdown through the plans owner API (apply_credit), suspend_tenant on
tenants/subscriptions, and the notifications insert dunning owns.

Legacy side: the committed transcripts under procs/transcripts/ (the recorded legacy post-state of
each scenario: pinned business fields plus the state probes), whose source/fixture fingerprints are
checked first. Target side: the DISPOSABLE procs namespace's billing-service + local mongo:7
(make procs-up NS=<ns>), reset from the legacy before-state with POST /internal/reset before each
scenario and driven through the service's HTTP API; this script itself only READS the local mongo
(find / find_one) and compares the documents with the transcripts and with the procedure semantics
of invoicing.sql / dunning.sql mirrored here. Neither the billing_ro source fixture nor Atlas is
touched, and no legacy database is written or called (see finding V8 in the report)."""
import hashlib, json, os, sys, urllib.request, zlib
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from pymongo import MongoClient

NS = os.environ.get("NS", "v3")
off = zlib.crc32(NS.encode()) % 1000
TARGET_PORT, MONGO_PORT = 12096 + off, 56432 + off
API = f"http://127.0.0.1:{TARGET_PORT}"
mongo = MongoClient(f"mongodb://127.0.0.1:{MONGO_PORT}/?directConnection=true", uuidRepresentation="standard", tz_aware=True)["billing_migration"]
sys.path.insert(0, "procs/harness")
from fingerprints import source_sha, fixture_sha  # noqa: E402
FP = {"source_sha": open("procs/transcripts/SOURCE_SHA").read().strip(), "fixture_sha": open("procs/transcripts/FIXTURE_SHA").read().strip()}

def api(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        raw = resp.read(); return resp.status, (json.loads(raw) if raw else None)
def reset_target():
    status, _ = api("POST", "/internal/reset"); assert status == 204, status
def q2(v): return str(Decimal(str(v.to_decimal() if hasattr(v, "to_decimal") else v)).quantize(Decimal("0.01")))
def d(v): return v.astimezone(timezone.utc).date().isoformat() if isinstance(v, datetime) else (v.isoformat() if isinstance(v, date) else v)
def md5uuid(*parts): return UUID(hashlib.md5("".join(parts).encode()).hexdigest())
def transcript(module, sid): return json.load(open(f"procs/transcripts/{module}/{sid}.json"))
def current(tr): return tr["source_sha"] == FP["source_sha"] and tr["fixture_sha"] == FP["fixture_sha"]

def mg_attempts():
    out = []
    for doc in mongo.invoices.find({}):
        for e in doc.get("dunningAttempts", []):
            out.append({"invoice_id": str(doc["_id"]), "tenant_id": str(e["tenantId"]), "attempt_no": e["attemptNo"], "scheduled_for": d(e["scheduledFor"]), "status": e["status"], "id": str(e["id"]), "invoice_tenant": str(doc["tenantId"]), "invoice_status": doc["status"]})
    return sorted(out, key=lambda r: (r["invoice_id"], r["attempt_no"]))
def mg_tenants(): return [{"id": str(t["_id"]), "status": t["status"]} for t in mongo.tenants.find({}, sort=[("_id", 1)])]
def mg_subs(): return [{"id": str(s["_id"]), "tenant_id": str(s["tenantId"]), "status": s["status"], "suspended_on": d(s.get("suspendedOn"))} for s in mongo.subscriptions.find({}, sort=[("_id", 1)])]
def mg_notifications(): return [{"id": str(n["_id"]), "tenant_id": str(n["tenantId"]), "kind": n["kind"], "sent_at": n["sentAt"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")} for n in mongo.notifications.find({}, sort=[("tenantId", 1), ("sentAt", 1)])]
def mg_credit_notes(tenant):
    t = mongo.tenants.find_one({"_id": tenant})
    return sorted([{"id": str(n["id"]), "issued_on": d(n["issuedOn"]), "amount": q2(n["amount"]), "remaining_amount": q2(n["remainingAmount"])} for n in t.get("creditNotes", [])], key=lambda n: (n["issued_on"], n["id"]))
def mg_invoice(period_id):
    doc = mongo.invoices.find_one({"periodId": period_id})
    if doc is None: return None
    return {"id": str(doc["_id"]), "status": doc["status"], "subtotal": q2(doc["subtotal"]), "tax": q2(doc["tax"]), "total": q2(doc["total"]), "issued_at": doc["issuedAt"].astimezone(timezone.utc).isoformat(),
            "lines": [{"id": str(l["id"]), "line_no": l["lineNo"], "line_type": l["lineType"], "description": l["description"], "amount": q2(l["amount"])} for l in sorted(doc["invoiceLines"], key=lambda l: l["lineNo"])],
            "dunning_attempts": len(doc.get("dunningAttempts", []))}
def mg_period(period_id):
    p = mongo.ratingPeriods.find_one({"_id": period_id})
    return None if p is None else {"id": str(p["_id"]), "has_rating": isinstance(p.get("rating"), dict), "billable_units": p["rating"]["billableUnits"] if isinstance(p.get("rating"), dict) else None}

T = lambda n: UUID(f"00000000-0000-0000-0000-00000000000{n}")
SEEDED_ATTEMPT = "80000000-0000-0000-0000-000000000001"
results = {"namespace": NS, "ports": {"billing_service": TARGET_PORT, "local_mongo": MONGO_PORT},
           "transcripts_current": {"source_sha_matches_procs_sql": source_sha() == FP["source_sha"], "fixture_sha_matches_schema_seed": fixture_sha() == FP["fixture_sha"]}, "scenarios": {}}
def record(name, **kw): results["scenarios"][name] = kw

# --- DUNNING-002 / DUNNING-003 (+ a second call on the same as_of): sp_schedule_dunning -> invoices.dunningAttempts via append_dunning_attempt
for sid, as_of, second in (("DUNNING-002", date(2026, 2, 14), None), ("DUNNING-003", date(2026, 2, 17), None), ("schedule_twice_same_as_of", date(2026, 2, 14), date(2026, 2, 14))):
    reset_target(); before = mg_attempts()
    api("POST", "/api/dunning/schedule-runs", {"as_of": as_of.isoformat()})
    if second: api("POST", "/api/dunning/schedule-runs", {"as_of": second.isoformat()})
    att = mg_attempts(); new = [a for a in att if a["id"] != SEEDED_ATTEMPT]
    overdue = sorted(str(x["_id"]) for x in mongo.invoices.find({"status": "overdue"}))
    expected_day = as_of + __import__("datetime").timedelta(days={6: 2, 7: 1}.get(as_of.isoweekday(), 0))
    checks = {"rows": len(att), "new_attempts_target": len(new),
              "one_new_attempt_per_overdue_invoice_per_call": sorted(a["invoice_id"] for a in new) == sorted(overdue * (2 if second else 1)),
              # per invoice, the new numbers are exactly prior_max+1 .. prior_max+calls (consecutive, no gap, no reuse)
              "new_attempt_nos_consecutive_from_prior_max": all(
                  sorted(a["attempt_no"] for a in new if a["invoice_id"] == inv) ==
                  list(range(max([b["attempt_no"] for b in before if b["invoice_id"] == inv], default=0) + 1,
                             max([b["attempt_no"] for b in before if b["invoice_id"] == inv], default=0) + 1 + (2 if second else 1)))
                  for inv in overdue),
              "ids_follow_md5_invoice_id_attempt_no_target": sum(1 for a in new if UUID(a["id"]) == md5uuid(a["invoice_id"], str(a["attempt_no"]))) == len(new),
              "scheduledFor_is_next_business_day_target": all(a["scheduled_for"] == expected_day.isoformat() for a in new),
              "status_scheduled_target": all(a["status"] == "scheduled" for a in new),
              "tenantId_eq_invoice_tenant_target": all(a["tenant_id"] == a["invoice_tenant"] for a in att),
              "duplicate_attempt_no_per_invoice_target": len(att) - len({(a["invoice_id"], a["attempt_no"]) for a in att}),
              "attempts_on_non_overdue_invoices_target": sum(1 for a in att if a["invoice_status"] != "overdue"),
              "seeded_attempt_untouched_target": [a for a in att if a["id"] == SEEDED_ATTEMPT] == [a for a in before if a["id"] == SEEDED_ATTEMPT]}
    tr = transcript("dunning", sid) if sid.startswith("DUNNING") else None
    if tr:
        probe_rows = [{k: a[k] for k in ("invoice_id", "attempt_no", "scheduled_for", "status")} for a in att]
        checks["target_eq_transcript_probe_schedule_rows"] = probe_rows == tr["probes"]["schedule_rows"]
        inv = "60000000-0000-0000-0000-000000000001" if sid == "DUNNING-002" else "60000000-0000-0000-0000-000000000002"
        last = max((a for a in att if a["invoice_id"] == inv), key=lambda a: a["attempt_no"])
        checks["target_eq_transcript_business_fields"] = {k: last[k] for k in tr["business_fields"]} == tr["business_fields"]
        checks["transcript_fingerprints_current"] = current(tr)
    record(sid, entrypoint="billing.sp_schedule_dunning", inputs={"as_of": as_of.isoformat(), "second_call": second.isoformat() if second else None}, legacy_transcript=(tr or {}).get("probes"), target_post_state=att, **checks)

# --- DUNNING-004 / DUNNING-005: sp_suspend_overdue -> tenants/subscriptions via suspend_tenant, notifications insert
for sid, twice in (("DUNNING-004", False), ("DUNNING-005", True)):
    as_of = date(2026, 2, 28)
    reset_target(); before_t, before_s, before_n = mg_tenants(), mg_subs(), mg_notifications()
    api("POST", "/api/dunning/suspension-runs", {"as_of": as_of.isoformat()})
    if twice: api("POST", "/api/dunning/suspension-runs", {"as_of": as_of.isoformat()})
    tt, ts, tn = mg_tenants(), mg_subs(), mg_notifications()
    tr = transcript("dunning", sid)
    susp = [n for n in tn if n["kind"] == "suspension"]
    changed_t = [b["id"] for a, b in zip(before_t, tt) if a != b]
    changed_s = [b for a, b in zip(before_s, ts) if a != b]
    # the procedure's predicate on the before-state: distinct tenants with an overdue invoice issued <= as_of - 14 that are still active
    cutoff = as_of - __import__("datetime").timedelta(days=14)
    exp = sorted({str(x["tenantId"]) for x in mongo.invoices.find({"status": "overdue"}) if x["issuedAt"].astimezone(timezone.utc).date() <= cutoff} & {t["id"] for t in before_t if t["status"] == "active"})
    checks = {"tenants_changed_target": changed_t, "suspended_now_target_eq_procedure_predicate": changed_t == exp,
              "changed_tenants_now_suspended": all(t["status"] == "suspended" for t in tt if t["id"] in changed_t),
              "subscriptions_changed_target": len(changed_s),
              "changed_subscriptions_belong_to_suspended_tenants_and_were_active": all(s["tenant_id"] in exp for s in changed_s) and all(a["status"] == "active" for a, b in zip(before_s, ts) if a != b),
              "changed_subscriptions_status_suspended_suspendedOn_as_of": all(s["status"] == "suspended" and s["suspended_on"] == as_of.isoformat() for s in changed_s),
              "tenant_2_already_suspended_untouched_target": next(t for t in tt if t["id"] == str(T(2))) == next(t for t in before_t if t["id"] == str(T(2))) and [s for s in ts if s["tenant_id"] == str(T(2))] == [s for s in before_s if s["tenant_id"] == str(T(2))],
              "suspension_notifications_target": len(susp), "one_suspension_notification_per_suspended_tenant": sorted(n["tenant_id"] for n in susp) == exp,
              "suspension_notification_ids_follow_md5_target": all(UUID(n["id"]) == md5uuid(n["tenant_id"], "suspension", as_of.isoformat()) for n in susp),
              "notification_unique_key_dupes_target": len(tn) - len({(n["tenant_id"], n["kind"], n["sent_at"]) for n in tn}),
              "seeded_dunning_notification_untouched_target": [n for n in tn if n["kind"] == "dunning"] == before_n,
              "target_eq_transcript_probe_suspension_notifications": susp == tr["probes"]["suspension_notifications"],
              "transcript_fingerprints_current": current(tr)}
    sub5 = [s for s in ts if s["tenant_id"] == str(T(5))]
    checks["target_eq_transcript_business_fields"] = ({"status": sub5[0]["status"], "suspended_on": sub5[0]["suspended_on"]} == tr["business_fields"]) if sid == "DUNNING-004" else ([n["kind"] for n in susp if n["tenant_id"] == str(T(5))] == tr["business_fields"]["notification_kinds"])
    record(sid, entrypoint="billing.sp_suspend_overdue", inputs={"as_of": as_of.isoformat(), "calls": 2 if twice else 1}, legacy_transcript=tr["probes"], target_post_state={"tenants": tt, "subscriptions": ts, "notifications": tn}, **checks)

# --- INVOICE-003 / 004 / 005: sp_issue_invoice -> tenants.creditNotes via apply_credit, ratingPeriods via finalize_rating, invoices
for sid, tenant in (("INVOICE-003", 9), ("INVOICE-004", 4), ("INVOICE-005", 6)):
    ps, pe, t = date(2026, 2, 1), date(2026, 2, 28), T(tenant)
    period_id = md5uuid(str(t), ps.isoformat())
    reset_target(); before_cn = mg_credit_notes(t); others_before = {n: mg_credit_notes(T(n)) for n in range(1, 10) if n != tenant}
    before_inv_count = mongo.invoices.count_documents({})
    api("POST", f"/api/tenants/{t}/invoices", {"period_start": ps.isoformat(), "period_end": pe.isoformat()})
    tcn, tinv, tper = mg_credit_notes(t), mg_invoice(period_id), mg_period(period_id)
    tr = transcript("invoicing", sid); bf = tr["business_fields"]
    avail = sum(Decimal(a["remaining_amount"]) for a in before_cn); drawn = avail - sum(Decimal(a["remaining_amount"]) for a in tcn)
    gross = Decimal(tinv["subtotal"]) + Decimal(tinv["tax"]) if tinv else None
    # legacy drawdown order: issued_on, id; a note is drawn only once every earlier note is exhausted
    order_ok = all(Decimal(tcn[i]["remaining_amount"]) == 0 for i in range(len(tcn)) if any(Decimal(tcn[j]["remaining_amount"]) < Decimal(tcn[j]["amount"]) for j in range(i + 1, len(tcn))))
    checks = {"credit_drawn_target": q2(drawn), "credit_drawn_eq_min_available_gross_target": tinv is not None and drawn == min(avail, gross),
              "drawdown_order_issuedOn_then_id_target": order_ok, "no_remaining_above_amount_or_below_zero_target": all(Decimal(0) <= Decimal(n["remaining_amount"]) <= Decimal(n["amount"]) for n in tcn),
              "credit_note_ids_and_amounts_unchanged_target": [(n["id"], n["amount"], n["issued_on"]) for n in tcn] == [(n["id"], n["amount"], n["issued_on"]) for n in before_cn],
              "other_tenants_credit_notes_unchanged_target": all(mg_credit_notes(T(n)) == v for n, v in others_before.items()),
              "invoice_created_target": tinv is not None and mongo.invoices.count_documents({}) == before_inv_count + 1,
              "invoice_id_follows_md5_period_id_invoice_target": tinv is not None and UUID(tinv["id"]) == md5uuid(str(period_id), "invoice"),
              "line_ids_follow_md5_invoice_id_line_no_target": tinv is not None and all(UUID(l["id"]) == md5uuid(tinv["id"], str(l["line_no"])) for l in tinv["lines"]),
              "lines_target": len((tinv or {}).get("lines", [])), "line_types_target": [l["line_type"] for l in (tinv or {}).get("lines", [])],
              "invoice_total_eq_subtotal_plus_tax_minus_credit_target": tinv is not None and Decimal(tinv["total"]) == gross - drawn,
              "credit_line_amount_eq_minus_drawn_target": tinv is not None and Decimal(next(l["amount"] for l in tinv["lines"] if l["line_type"] == "credit")) == -drawn,
              "issuedAt_eq_period_end_target": tinv is not None and tinv["issued_at"] == datetime(pe.year, pe.month, pe.day, tzinfo=timezone.utc).isoformat(),
              "dunning_attempts_empty_on_new_invoice_target": (tinv or {}).get("dunning_attempts") == 0,
              "rating_period_finalized_target": tper is not None and tper["has_rating"],
              "target_eq_transcript_probe_invoice_state": tinv is not None and [{"status": tinv["status"], "subtotal": tinv["subtotal"], "tax": tinv["tax"], "total": tinv["total"]}] == tr["probes"]["invoice_state"],
              "transcript_fingerprints_current": current(tr)}
    if sid in ("INVOICE-003", "INVOICE-004"):
        checks["target_eq_transcript_business_fields"] = {"credit_ids": [n["id"] for n in tcn], "issued_on": [n["issued_on"] for n in tcn], "remaining": [n["remaining_amount"] for n in tcn]} == bf
    else:
        checks["target_eq_transcript_business_fields"] = tinv is not None and {"status": tinv["status"], "tax": tinv["tax"], "total": tinv["total"]} == bf
    record(sid, entrypoint="billing.sp_issue_invoice", inputs=tr["inputs"], legacy_transcript={"business_fields": bf, "probes": tr["probes"]}, target_post_state={"credit_notes_before": before_cn, "credit_notes": tcn, "invoice": tinv, "rating_period": tper}, **checks)

reset_target()
MUST_BE_ZERO = ("duplicate_attempt_no_per_invoice_target", "attempts_on_non_overdue_invoices_target", "notification_unique_key_dupes_target")
INFO = ("rows", "new_attempts_target", "tenants_changed_target", "subscriptions_changed_target", "suspension_notifications_target", "credit_drawn_target", "lines_target", "line_types_target")
flags = [f"{k}.{c}" for k, v in results["scenarios"].items() for c, val in v.items()
         if c not in ("entrypoint", "inputs", "legacy_transcript", "target_post_state") and ((c in MUST_BE_ZERO and val) or (c not in MUST_BE_ZERO and c not in INFO and val is not True))]
results["summary"] = {"scenarios": list(results["scenarios"]), "all_checks_pass": not flags and all(results["transcripts_current"].values()), "failed": flags,
                      "legacy_side": "committed transcripts (recorded legacy post-state); no legacy database was written or called", "atlas_touched": False}
print(json.dumps(results, indent=1, default=str))
