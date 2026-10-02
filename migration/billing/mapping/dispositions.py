"""Oracle-specific construct dispositions for plan step s3.2-known-incompatibilities.

One disposition per construct the census found (census.json#source_units[*].oracle_constructs,
#source_units[*].package_state_globals, #triggers, #sequences, #scheduler_jobs) plus the three
column-level representations the step names (DD-MON-YY text dates, CSV id lists, *_CD codes).
build_mapping_spec.py folds the result into mapping_spec.json#incompatibilities and fails when a
census construct has no disposition or a disposition names an object the census did not find.

Cites are relative to services/legacy-billing/db/oracle/. Nothing here touches Oracle or the
tolerances; a hit whose default would have done so is recorded as a decision instead.
"""
from __future__ import annotations

PLAN_STEP = "s3.2-known-incompatibilities"

# Every swallowed-error site, each one a behavior difference for review. The census regex
# (WHEN OTHERS THEN NULL) finds two; f_str2dt (RETURN NULL), log_msg (ROLLBACK) and the purge job
# body swallow the same way and are listed with it.
BEHAVIOR_DIFFERENCES = [
    {"id": "bd-fn-entitlement-swallow", "construct": "when_others_null", "status": "for-review",
     "cite": "packages/02_pkg_plans.sql:40-50",
     "oracle": "fn_entitlement: the plan-code lookup (comma join with (+), ROWNUM = 1) is wrapped in WHEN OTHERS THEN NULL; NO_DATA_FOUND and every other error leave g_last_plan_code at the value of the PREVIOUS call in the same session",
     "mongo": "stateless lookup; no covering subscription is an explicit empty result, a lookup error is raised to the caller; the stale-previous-plan side effect no longer exists",
     "visible_change": "a tenant with no covering subscription can no longer be reported under another tenant's plan code; errors surface instead of an empty cursor"},
    {"id": "bd-schedule-dunning-swallow", "construct": "when_others_null", "status": "for-review",
     "cite": "packages/05_pkg_dunning.sql:52-64",
     "oracle": "sp_schedule_dunning: the per-invoice INSERT INTO dunning_attempts is wrapped in WHEN OTHERS THEN NULL; a failing row is skipped silently and the batch commits the rest",
     "mongo": "a duplicate on uq_dunning_attempts_invoice_attempt is reported as 'already scheduled' in the run result; any other insert error aborts the run with the error and is reported",
     "visible_change": "/api/dunning/schedule can fail where Oracle silently scheduled a subset; the number of attempts written is reported instead of implied"},
    {"id": "bd-f-str2dt-swallow", "construct": "to_char_to_date", "status": "for-review",
     "cite": "packages/01_pkg_util.sql:55-61",
     "oracle": "f_str2dt: TO_DATE(p_str, 'DD-MON-YY') under WHEN OTHERS THEN RETURN NULL (not matched by the census regex, same swallow); an unparsable text reads as NULL",
     "mongo": "loader: typed *Date sibling absent, verbatim text kept, the (collection, _id, field, text) tuple written to the run's quarantine report; app: a parse failure is an explicit validation error, never NULL and never a guessed date",
     "visible_change": "50 fixture dirty_dates rows are reported, not silently NULL; new writes with a bad date are rejected"},
    {"id": "bd-log-msg-swallow", "construct": "autonomous_transaction", "status": "for-review",
     "cite": "packages/01_pkg_util.sql:66-77",
     "oracle": "log_msg: WHEN OTHERS THEN ROLLBACK; an audit insert failure is invisible to the caller",
     "mongo": "the audit insert still runs outside the business transaction, but its failure is raised to the caller as an explicit error",
     "visible_change": "a business call (including read-only list_plans / usage_rating / invoice_preview) fails when the audit insert fails; keeping log-and-continue instead is a new decision for the reviewer"},
    {"id": "bd-purge-job-swallow", "construct": "JOB_PURGE_AUDIT_LOG", "status": "retired-with-job",
     "cite": "schema/04_jobs.sql:21-30",
     "oracle": "job body: DELETE ... older than 90 days under EXCEPTION WHEN OTHERS THEN NULL (job created DISABLED, run_count 0)",
     "mongo": "no replacement under d-audit-retention = match-live; nothing to swallow",
     "visible_change": "none (the job never ran live)"},
    {"id": "bd-overdue-status-owner", "construct": "status_cd_codes", "status": "open",
     "cite": "packages/05_pkg_dunning.sql:17-99; access_patterns.md 2.10",
     "oracle": "every dunning path selects invoices.status_cd = 40 (and sp_suspend_overdue acts on it), but no entrypoint, trigger or job ever writes 40 (or 30): the only transition the app writes is 20 in sp_issue_invoice; 40 arrives from seed/ops SQL",
     "mongo": "the spec carries statusCd verbatim and the dunning queries unchanged; nobody in the application sets 40 after cutover",
     "visible_change": "post-cutover overdue detection stops unless an owner is named; this spec names none (ops SQL against Atlas, an app transition on issuedAt age, or the mainframe feed are the candidates) and lists it as an open behavior difference for the manager",
     "owner_after_cutover": None},
    {"id": "bd-uncancel-trigger", "construct": "TRG_SUB_NO_UNCANCEL", "status": "for-review",
     "cite": "schema/01_tables.sql:228-236",
     "oracle": "BEFORE UPDATE OF status_cd: when :OLD.status_cd = 30 the trigger silently forces :NEW.status_cd back to 30; the UPDATE reports 1 row and the caller never learns the change was discarded",
     "mongo": "service invariant: every subscription status update filters {statusCd: {$ne: 30}}; matchedCount 0 on a cancelled row is returned as an explicit 'cancelled subscription unchanged' outcome",
     "visible_change": "sp_change_plan / sp_suspend_overdue callers see the no-op instead of a silent one"},
    {"id": "bd-usage-check-trigger", "construct": "TRG_USAGE_EVENTS_CHECK", "status": "parity",
     "cite": "schema/01_tables.sql:239-253",
     "oracle": "BEFORE INSERT: RAISE_APPLICATION_ERROR -20001 'units must be > 0' / -20002 'unknown usage kind'",
     "mongo": "service validation before the insert plus validator {units: {$gt: 0}, kindCd: int}; the same two messages are returned as 400s",
     "visible_change": "none intended; the error originates in the service, not the database"},
    {"id": "bd-yyyymmdd-compare", "construct": "to_char_to_date", "status": "parity",
     "cite": "packages/03_pkg_rating.sql:79-80,153-155; packages/05_pkg_dunning.sql:28,76-77",
     "oracle": "TIMESTAMP(6) columns compared as TO_CHAR(..., 'YYYYMMDD') strings, i.e. by calendar day in the session time zone",
     "mongo": "typed date compare against day bounds: occurredAt >= day(start) and < day(end) + 1 day; issuedAt < day(asOf); issuedAt < day(asOf) - 13 days (day bounds in the zone the service is configured with, which must equal the Oracle session zone the facade wrote in)",
     "visible_change": "none for whole-day inputs; ix_usage_events_tenant_occurred / ix_invoices_status_issued become usable (a string compare could not use an index)"},
    {"id": "bd-suspend-overdue-txn-scope", "construct": "cursor_loop", "status": "for-review",
     "cite": "packages/05_pkg_dunning.sql:71-99",
     "oracle": "sp_suspend_overdue: one commit for every tenant in the sweep (and, under JOB_NIGHTLY_DUNNING, shared with sp_schedule_dunning)",
     "mongo": "one multi-document transaction per tenant (tenants + subscriptions + subscriptions_hist + notifications); a failure stops the sweep after the tenants already committed; uq_notifications_tenant_kind_sent makes the rerun idempotent",
     "visible_change": "a partially completed sweep is possible and is reported per tenant"},
    {"id": "bd-nightly-job-scheduler", "construct": "JOB_NIGHTLY_DUNNING", "status": "for-review",
     "cite": "schema/04_jobs.sql:10-19",
     "oracle": "DBMS_SCHEDULER 02:00 daily: sp_schedule_dunning then sp_suspend_overdue; created DISABLED, run_count 0",
     "mongo": "a billing-service scheduled job calling the two replacements in order, shipped disabled (match-live); enabling it is an ops action after cutover",
     "visible_change": "none until enabled"},
    {"id": "bd-package-state", "construct": "package_state_globals", "status": "parity",
     "cite": "packages/01_pkg_util.sql..05_pkg_dunning.sql (g_* declarations)",
     "oracle": "22 session-scoped package globals; only PKG_RATING's are read across calls, and only inside the same procedure call chain (compute_rating -> sp_finalize_rating / fn_invoice_preview); the rest are write-only diagnostics",
     "mongo": "stateless replacements return the rating result as a value; no session state",
     "visible_change": "none (no entrypoint observes a global set by an earlier call, fn_entitlement's stale plan code excepted - see bd-fn-entitlement-swallow)"},
]


def incompatibilities(census: dict, buckets: dict) -> dict:
    units = census["source_units"]
    found = sorted({c for u in units.values() for c in u.get("oracle_constructs", [])})
    globals_by_pkg = {k.split(":", 1)[1]: v["package_state_globals"] for k, v in units.items()
                      if v.get("package_state_globals")}
    triggers = {t["trigger_name"]: t for t in census["triggers"]}
    sequences = {s["sequence_name"]: s for s in census["sequences"]}
    jobs = {j["job_name"]: j for j in census["scheduler_jobs"]}
    bucket_of = {k.split(":", 1)[1]: v for k, v in buckets["objects"].items()}

    def where(c):
        return sorted(k for k, u in units.items() if c in u.get("oracle_constructs", []))

    def construct(cid, kind, disposition, mongo, oracle, **extra):
        return {"id": cid, "kind": kind, "found_in": extra.pop("found_in", where(cid)),
                "oracle": oracle, "disposition": disposition, "mongo": mongo, **extra}

    def trigger(name, disposition, mongo, oracle, **extra):
        t = triggers[name]
        b = bucket_of[name]
        return construct(name, "trigger", disposition, mongo, oracle,
                         found_in=[f"TRIGGER:{name} ({t['trigger_type']} {t['triggering_event']} ON {t['table_name']})"],
                         census_bucket=b["bucket"], cite=b["cite"], **extra)

    def sequence(name, mongo):
        s = sequences[name]
        b = bucket_of[name]
        return construct(name, "sequence", "retire; existing values carried, new values app-issued (key_strategy.sequence_ids)", mongo,
                         f"{name} last_number {s['last_number']}, cache {s['cache_size']}",
                         found_in=[f"SEQUENCE:{name}"], census_bucket=b["bucket"], cite=b["cite"])

    constructs = [
        # --- PL/SQL constructs (census regexes) ---------------------------------------------
        construct("autonomous_transaction", "plsql", "migrate-as-logic: keep the write outside the business transaction",
                  "billing_audit_log insert issued on its own session (no transaction) before/after the business transaction, never inside it; failure raised (bd-log-msg-swallow)",
                  "PRAGMA AUTONOMOUS_TRANSACTION in pkg_ow_util.log_msg: the audit row commits even when the caller rolls back",
                  cite="packages/01_pkg_util.sql:66-77", behavior_differences=["bd-log-msg-swallow"]),
        construct("cursor_loop", "plsql", "migrate-as-logic: row-at-a-time loops become set operations or application loops inside the unit's transaction",
                  "compute_rating / fn_usage_summary -> $match + $group on usage_events; sp_issue_invoice line loop -> one invoices document; sp_change_plan close-out loop -> updateMany; dunning loops -> per-invoice / per-tenant application loops (bd-suspend-overdue-txn-scope)",
                  "OPEN/FETCH and FOR r IN (...) loops in four package bodies",
                  behavior_differences=["bd-suspend-overdue-txn-scope"]),
        construct("decode", "plsql", "migrate-as-logic: DECODE becomes application code or $switch; code text comes from the codes collection",
                  "status/kind decoding reads codes (compound _id {codeType, codeVal}); weekday roll in sp_schedule_dunning (DECODE on TO_CHAR 'DY') becomes a date-library weekday check in the service",
                  "DECODE(...) for inline code decoding and the weekday roll (packages/05_pkg_dunning.sql:47-50)"),
        construct("execute_immediate", "plsql", "migrate-as-logic: dynamic SQL over static statements becomes plain driver calls",
                  "f_code_desc -> codes.findOne({_id: {codeType, codeVal}}) with 'UNKNOWN(<val>)' on miss; sp_issue_invoice DELETE invoice_lines -> replaced by writing invoices.lines whole; sp_change_plan INSERT -> subscriptions.insertOne",
                  "EXECUTE IMMEDIATE for a static lookup (01_pkg_util.sql:41), a static DELETE (04_pkg_invoicing.sql:149) and a static INSERT (02_pkg_plans.sql:103)"),
        construct("nvl", "plsql", "migrate-as-logic: NVL defaults applied in the service; stored values stay absent when NULL (d-null-absent)",
                  "$ifNull / application defaults at read time (NVL(active_yn,'N'), NVL(units,0), NVL(ends_on, 31-DEC-99), NVL(MAX(attempt_no),0)+1); the sentinel date 31-DEC-99 is not stored",
                  "NVL(...) in every package body and in TRG_CUSTOMER_MASTER_SEQ / TRG_USAGE_EVENTS_CHECK"),
        construct("oracle_outer_join", "plsql", "migrate-as-logic: (+) joins become $lookup or a second read",
                  "fn_overdue_accounts invoices (+) tenants -> $lookup tenants (preserveNullAndEmptyArrays); fn_entitlement subscriptions (+) plans -> $lookup plans",
                  "old-style (+) outer joins in pkg_plans and pkg_dunning"),
        construct("raise_application_error", "plsql", "migrate-as-logic: trigger-raised errors become service validation with the same messages",
                  "see TRG_USAGE_EVENTS_CHECK (bd-usage-check-trigger)",
                  "RAISE_APPLICATION_ERROR(-20001/-20002) in TRG_USAGE_EVENTS_CHECK",
                  behavior_differences=["bd-usage-check-trigger"]),
        construct("sequence_nextval", "plsql", "retire: SEQ_*.NEXTVAL in triggers replaced by app-issued ids",
                  "key_strategy.sequence_ids: carried values kept as BSON long; new values from the app allocator seeded at max+1; no counters collection, no ObjectId",
                  "SEQ_*.NEXTVAL in the five key/history triggers"),
        construct("sys_refcursor", "plsql", "migrate-as-logic: ref cursors become result arrays / cursors from the driver",
                  "each fn_* replacement returns the projected documents (find/aggregate cursor) in the same column order the facade reads today",
                  "every fn_* entrypoint returns SYS_REFCURSOR consumed by the facade"),
        construct("sysdate", "plsql", "migrate-as-logic: database clock replaced by the application clock (UTC)",
                  "history histDt text and histDate are stamped by the service at write time; billing_audit_log.loggedAt is set by the service (Oracle DEFAULT SYSDATE on logged_at)",
                  "SYSDATE in TRG_SUBSCRIPTIONS_HIST / TRG_CUSTOMER_MASTER_HIST and as a column default on BILLING_AUDIT_LOG.LOGGED_AT"),
        construct("to_char_to_date", "plsql", "migrate-as-logic: text<->date conversions become typed values; the two text formats that are stored stay stored verbatim",
                  "DD-MON-YY column text: see dd_mon_yy_string_dates; 'DD-MON-YY HH24:MI:SS' histDt: written by the service in the same format plus histDate; YYYYMMDD compares: typed day-bound compares (bd-yyyymmdd-compare); f_str2dt NULL-on-error: bd-f-str2dt-swallow; f_md5_uuid inputs TO_CHAR(date,'YYYY-MM-DD') reproduced byte-for-byte so derived ids match",
                  "TO_CHAR / TO_DATE in every package body and both history triggers",
                  behavior_differences=["bd-f-str2dt-swallow", "bd-yyyymmdd-compare"]),
        construct("utl_raw_or_dbms", "plsql", "migrate-as-logic: STANDARD_HASH MD5 reproduced in the service",
                  "f_md5_uuid(p) = lowercase hex md5 of the UTF-8 bytes of p; the service uses the same function so rating_periods / rating_periods.result / invoices.lines[].id / dunning_attempts._id / subscriptions._id values are identical",
                  "UTL_RAW.CAST_TO_RAW + STANDARD_HASH(..., 'MD5') in pkg_ow_util.f_md5_uuid (packages/01_pkg_util.sql:26)"),
        construct("when_others_null", "plsql", "migrate-as-logic: every swallowed error surfaces as an explicit error; each site is a behavior difference for review",
                  "see behavior_differences bd-fn-entitlement-swallow, bd-schedule-dunning-swallow (regex hits) and bd-f-str2dt-swallow, bd-log-msg-swallow, bd-purge-job-swallow (same pattern, other spelling)",
                  "WHEN OTHERS THEN NULL in pkg_plans.fn_entitlement and pkg_dunning.sp_schedule_dunning",
                  behavior_differences=["bd-fn-entitlement-swallow", "bd-schedule-dunning-swallow", "bd-f-str2dt-swallow", "bd-log-msg-swallow", "bd-purge-job-swallow"]),
    ]

    # --- package-state globals: one disposition per package -------------------------------
    role = {
        "PKG_OW_UTIL": "write-only diagnostics (call counter, last module/uuid); dropped",
        "PKG_PLANS": "g_last_tenant_id write-only; g_last_plan_code is the fn_entitlement result and keeps its previous value on a swallowed error (bd-fn-entitlement-swallow); dropped",
        "PKG_RATING": "compute_rating's result (used/quota/rollover/billable/overage, tiers, period) read by sp_finalize_rating and fn_invoice_preview in the same call chain; becomes a value returned by the rating function",
        "PKG_INVOICING": "fn_invoice_preview's running totals (fee, overage, credit, tax, plan code) consumed in the same call; becomes local state of the preview function",
        "PKG_DUNNING": "write-only diagnostics (last run date, scheduled count); the count becomes the run result returned to the caller",
    }
    for pkg, names in sorted(globals_by_pkg.items()):
        constructs.append(construct(f"package_state_globals:{pkg}", "package-state", "migrate-as-logic: stateless service; no session-scoped state",
                                    role[pkg], f"{len(names)} package globals: {', '.join(names)}", found_in=[f"PACKAGE:{pkg}"],
                                    cite=bucket_of[pkg]["cite"], behavior_differences=["bd-package-state"]))

    # --- triggers --------------------------------------------------------------------------
    constructs += [
        trigger("TRG_SUBSCRIPTIONS_HIST", "migrate-as-logic: app-side history write in the same transaction",
                "change_plan / suspend_overdue insert the pre-image into subscriptions_hist (histDt text + histDate, histOp 'U'/'D', app-issued _id) inside the unit's multi-document transaction",
                "AFTER UPDATE OR DELETE full-row copy into SUBSCRIPTIONS_HIST with TO_CHAR(SYSDATE,'DD-MON-YY HH24:MI:SS')"),
        trigger("TRG_CUSTOMER_MASTER_HIST", "migrate-as-logic: app-side history write in the same transaction",
                "any future customer update inserts the 155-column pre-image into customers_hist in the same transaction (no app write path exists today; 0 live rows)",
                "AFTER UPDATE OR DELETE 155-column copy into CUSTOMER_MASTER_HIST"),
        trigger("TRG_SUB_NO_UNCANCEL", "migrate-as-logic: service invariant",
                "subscription status updates filter {statusCd: {$ne: 30}}; cancelled rows are never modified and the caller is told (bd-uncancel-trigger)",
                "BEFORE UPDATE: silently keeps status_cd 30", behavior_differences=["bd-uncancel-trigger"]),
        trigger("TRG_USAGE_EVENTS_CHECK", "migrate-as-logic: service validation + collection validator",
                "units > 0 and kindCd present in codes('USAGE_KIND') checked by the service before insertOne; validator enforces units > 0 and the int type (bd-usage-check-trigger)",
                "BEFORE INSERT: RAISE_APPLICATION_ERROR on units <= 0 or unknown kind_cd", behavior_differences=["bd-usage-check-trigger"]),
        trigger("TRG_CUSTOMER_MASTER_SEQ", "split: id assignment retired with SEQ_CUSTOMER_MASTER, derivations kept in the service",
                "custSeqNo app-issued (max+1); custNameUpper = UPPER(custName) and rowVersionNo default 1 computed by the service on insert; the loader carries the live values verbatim",
                "BEFORE INSERT: seq_customer_master.NEXTVAL into cust_seq_no when NULL, cust_name_upper := UPPER(cust_name), row_version_no := NVL(.., 1)"),
        trigger("TRG_BILLING_AUDIT_LOG_ID", "retire: pure key assignment",
                "billing_audit_log._id app-issued (max+1) by the log_msg replacement", "BEFORE INSERT: seq_billing_audit_log.NEXTVAL into log_id"),
        trigger("TRG_ENTITY_ATTR_VALUE_SEQ", "retire: pure key assignment",
                "customers.attributes[].eavId app-issued (max+1) if an attribute write path ever exists; none does today", "BEFORE INSERT: seq_entity_attr_value.NEXTVAL into eav_id"),
    ]

    # --- sequences -------------------------------------------------------------------------
    constructs += [sequence(name, lands) for name, lands in sorted({
        "SEQ_BILLING_AUDIT_LOG": "billing_audit_log._id", "SEQ_CUSTOMER_MASTER": "customers.custSeqNo",
        "SEQ_CUSTOMER_MASTER_HIST": "customers_hist._id", "SEQ_ENTITY_ATTR_VALUE": "customers.attributes[].eavId",
        "SEQ_SUBSCRIPTIONS_HIST": "subscriptions_hist._id"}.items())]

    # --- scheduler jobs --------------------------------------------------------------------
    for name, disposition, mongo, bds in [
        ("JOB_NIGHTLY_DUNNING", "migrate-as-logic: billing-service scheduled job, shipped disabled (match-live)",
         "schedule_dunning then suspend_overdue replacements, each in its own transactions (atomic_units); enabling is an ops action", ["bd-nightly-job-scheduler", "bd-overdue-status-owner"]),
        ("JOB_PURGE_AUDIT_LOG", "retire; retention per d-audit-retention = match-live (no TTL, no purge)",
         "billing_audit_log keeps every document; a TTL index on loggedAt (expireAfterSeconds 7,776,000) is added only if the human picks ttl-90d; the census bucket note's TTL replacement is superseded by that decision", ["bd-purge-job-swallow"]),
    ]:
        j = jobs[name]
        b = bucket_of[name]
        constructs.append(construct(name, "scheduler-job", disposition, mongo,
                                    f"{j['repeat_interval']}, {j['state']}, run_count {j['run_count']}: {j['job_action']}",
                                    found_in=[f"JOB:{name}"], census_bucket=b["bucket"], cite=b["cite"], behavior_differences=bds))

    # --- column representations the step names -------------------------------------------
    tables = {t["name"]: t for t in census["tables"]}
    dt_cols = sorted(f"{tn}.{c['column_name']}" for tn, t in tables.items() for c in t["columns"]
                     if c["data_type"] == "VARCHAR2" and c["column_name"].endswith("_DT"))
    csv_cols = sorted(f"{tn}.{c['column_name']}" for tn, t in tables.items() for c in t["columns"]
                      if c["column_name"] in ("RELATED_ACCT_IDS", "CHILD_ACCT_IDS", "PROMO_CODES_CSV", "GL_ACCT_CSV"))
    cd_cols = sorted(f"{tn}.{c['column_name']}" for tn, t in tables.items() for c in t["columns"]
                     if c["column_name"].endswith("_CD") and tn != "FIXTURE_META")
    constructs += [
        construct("dd_mon_yy_string_dates", "column", "parse to a typed date; unparsable values quarantined, never guessed",
                  "verbatim text field + typed *Date sibling parsed under the Oracle RR rule only (the rule f_str2dt applies); on failure the sibling is absent and the loader writes the tuple to the run's quarantine report (bd-f-str2dt-swallow); the verbatim text is the recon value",
                  f"{len(dt_cols)} VARCHAR2 *_DT columns holding 'DD-MON-YY' text (fixture legacy_representations.dd_mon_yy_string_dates; 50 dirty_dates rows)",
                  found_in=dt_cols, behavior_differences=["bd-f-str2dt-swallow"]),
        construct("csv_id_lists", "column", "split to an array when the text matches the clean form; otherwise verbatim only",
                  "verbatim text field + *List array sibling (CSV_CLEAN forms in build_mapping_spec.py); 31 malformed_csv_lists rows keep the text and no array; the verbatim text is the recon value",
                  f"{len(csv_cols)} comma-separated id/code columns", found_in=csv_cols),
        construct("status_cd_codes", "column", "keep the integer codes; CODES migrated as the codes lookup collection",
                  "*_CD fields stay int; codes has compound _id {codeType, codeVal} and is loaded once per run; decoding is a $lookup / findOne exactly where Oracle joined CODES; overdue 40 ownership is open (bd-overdue-status-owner)",
                  f"{len(cd_cols)} *_CD magic-number columns decoded through CODES (code_type, code_val)",
                  found_in=cd_cols, behavior_differences=["bd-overdue-status-owner"]),
    ]

    # --- coverage: every census construct dispositioned exactly once -----------------------
    ids = [c["id"] for c in constructs]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"duplicate dispositions: {sorted(i for i in ids if ids.count(i) > 1)}")
    expected = set(found) | {f"package_state_globals:{p}" for p in globals_by_pkg} | set(triggers) | set(sequences) | set(jobs)
    named = {"dd_mon_yy_string_dates", "csv_id_lists", "status_cd_codes"}
    missing = expected - set(ids)
    unknown = set(ids) - expected - named
    if missing or unknown:
        raise SystemExit(f"disposition coverage: missing {sorted(missing)} unknown {sorted(unknown)}")
    bd_ids = {b["id"] for b in BEHAVIOR_DIFFERENCES}
    referenced = {b for c in constructs for b in c.get("behavior_differences", [])}
    if referenced != bd_ids:
        raise SystemExit(f"behavior differences unreferenced {sorted(bd_ids - referenced)} / undefined {sorted(referenced - bd_ids)}")
    for c in constructs:
        if not c["found_in"]:
            raise SystemExit(f"disposition {c['id']} has no census hit")

    return {
        "plan_step": PLAN_STEP,
        "rule": "one disposition per Oracle-specific construct the census found; defaults from the step (dates parsed/quarantined, CSV to arrays, codes kept + codes collection, sequences/trg_*_seq -> app ids, _hist triggers -> same-transaction history writes, swallowed errors -> explicit errors listed for review, multi-table PL/SQL writes -> multi-document transactions); a hit whose default would touch Oracle or tolerances.json is a decision, not a change",
        "coverage": {"census_constructs": len(found), "package_state_groups": len(globals_by_pkg), "triggers": len(triggers),
                     "sequences": len(sequences), "scheduler_jobs": len(jobs), "column_representations": len(named),
                     "dispositions": len(constructs), "behavior_differences": len(BEHAVIOR_DIFFERENCES),
                     "open": sorted(b["id"] for b in BEHAVIOR_DIFFERENCES if b["status"] == "open")},
        "constructs": constructs,
        "behavior_differences": BEHAVIOR_DIFFERENCES,
        "multi_table_writes": {
            "issue_invoice": "multi-document transaction over rating_periods, invoices, credit_notes (atomic_units.issue_invoice)",
            "finalize_rating": "single-document write: period + embedded result (d-embed-rating-result); atomic by construction",
            "change_plan": "multi-document transaction over subscriptions + subscriptions_hist",
            "dunning": "schedule_dunning: single-document inserts (one transaction per invoice is unnecessary: one document); suspend_overdue: one multi-document transaction per tenant (bd-suspend-overdue-txn-scope)",
            "audit": "never inside any of the above (autonomous_transaction)",
        },
    }
