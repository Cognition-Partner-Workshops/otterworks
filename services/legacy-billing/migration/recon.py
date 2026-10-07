#!/usr/bin/env python3
"""Reconcile the PostgreSQL billing target against the Oracle OW_BILLING estate.

    make billing-pg-recon NS=demo

Every value on the Postgres side is recomputed from the target tables; every
expected value is read live from Oracle (or, for the seed checks, from the
seed manifest). Before the checks run, migrate.py is executed a second time
and the target is fingerprinted before and after to prove the load is
idempotent. Once the app has written to Postgres after cutover the rerun is
refused and recon exits without a report, so it never erases those writes.

Writes <out>/<unit>.<ns>.recon.json (recon-report.schema.json) and a
Markdown table with one row per table and check.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import estate  # noqa: E402
import migrate  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
UNIT = "legacy-billing-oracle-to-postgres"
MANIFESTS = ROOT / "testdata" / "legacy" / "manifests"
ORACLE = "oracle:OW_BILLING"
DEFAULT_OUT = ROOT / "docs" / "tech-partnerships" / "recon"

# The planted anomalies are detected the same way on both sides.
DIRTY_DATE_SQL = {
    "oracle": "SELECT COUNT(*) FROM customer_master WHERE conversion_batch_no = :1"
              " AND signup_dt IS NOT NULL AND pkg_ow_util.f_str2dt(signup_dt) IS NULL",
    "postgres": "SELECT count(*) FROM customer_master WHERE conversion_batch_no = %s"
                " AND signup_dt IS NOT NULL AND pkg_ow_util.f_str2dt(signup_dt) IS NULL",
}
BAD_CSV_SQL = {
    "oracle": "SELECT COUNT(*) FROM customer_master WHERE conversion_batch_no = :1"
              " AND related_acct_ids IS NOT NULL"
              " AND NOT REGEXP_LIKE(related_acct_ids, '^[0-9]{5}(,[0-9]{5})*$')",
    "postgres": "SELECT count(*) FROM customer_master WHERE conversion_batch_no = %s"
                " AND related_acct_ids IS NOT NULL"
                " AND related_acct_ids !~ '^[0-9]{5}(,[0-9]{5})*$'",
}


def batch_no(ns: str) -> int:
    import hashlib
    return int(hashlib.sha256(ns.encode()).hexdigest()[:8], 16) % 90_000_000 + 1_000_000


def ora_one(ora, sql: str, params=()):
    with ora.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def ora_rows(ora, sql: str, params=()):
    with ora.cursor() as cur:
        cur.arraysize = 10_000
        cur.prefetchrows = 10_001
        cur.execute(sql, params)
        while True:
            batch = cur.fetchmany()
            if not batch:
                return
            yield from batch


def pg_one(pg, sql: str, params=()):
    return pg.execute(sql, params).fetchone()


def money(value) -> str:
    return "NULL" if value is None else estate.canon_decimal(Decimal(value))


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, table: str, check: str, expected, actual, ok: bool,
            source: str, detail: str = "") -> None:
        entry = {
            "id": f"{table}.{check}",
            "table": table,
            "check": check,
            "expected": expected,
            "actual": actual,
            "source_of_truth": source,
            "result": "pass" if ok else "fail",
        }
        if detail:
            entry["detail"] = detail
        self.checks.append(entry)


def checksum_rows(rows) -> estate.SetChecksum:
    ck = estate.SetChecksum()
    for row in rows:
        ck.add_row(row)
    return ck


def idempotency_rerun() -> dict:
    with estate.pg_connect() as pg:
        before = migrate.target_fingerprint(pg)
    migrate.migrate(verbose=False)
    with estate.pg_connect() as pg:
        after = migrate.target_fingerprint(pg)
    changed = sorted(k for k in before if before[k] != after.get(k))
    populated = any(not v.startswith("0:") for v in before.values())
    ok = populated and not changed
    import hashlib
    digest = hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest()[:16]
    evidence = (
        f"migrate.py executed again against the loaded target; {len(after)} objects "
        f"({len(after) - len(estate.SEQUENCES)} tables + {len(estate.SEQUENCES)} sequences) fingerprinted before and after "
        f"(row count + order-independent md5 of every column): "
        + ("identical" if not changed else f"changed: {', '.join(changed)}")
        + f"; fingerprint sha256[:16]={digest}"
    )
    return {"performed": True, "result": "pass" if ok else "fail", "evidence": evidence}


def table_checks(report: Report, ora, pg, table: estate.Table) -> None:
    name = table.name
    upper = name.upper()
    src = f"{ORACLE}.{upper}"
    columns = estate.pg_columns(pg, name)
    names = [c.name for c in columns]
    oracle_names = estate.oracle_columns(ora, name)
    report.add(name, "columns", len(oracle_names), len(names),
               sorted(oracle_names) == sorted(names), src,
               "same column names on both sides" if sorted(oracle_names) == sorted(names)
               else f"oracle-only={sorted(set(oracle_names) - set(names))} "
                    f"postgres-only={sorted(set(names) - set(oracle_names))}")

    targets = [name, estate.ORPHAN_TABLE] if table.split else [name]
    o_count = ora_one(ora, f"SELECT COUNT(*) FROM {name}")[0]
    p_counts = [pg_one(pg, f"SELECT count(*) FROM {t}")[0] for t in targets]
    split = " + ".join(str(c) for c in p_counts)
    report.add(name, "row_count", o_count, sum(p_counts), o_count == sum(p_counts), src,
               f"{o_count} = {split} ({' + '.join(targets)})" if table.split else "")

    for col in estate.sum_columns(columns):
        o_sum = ora_one(ora, f"SELECT SUM({col}) FROM {name}")[0]
        p_sums = [pg_one(pg, f"SELECT sum({col}) FROM {t}")[0] for t in targets]
        p_total = None if all(s is None for s in p_sums) else sum(s or 0 for s in p_sums)
        report.add(name, f"sum({col})", money(o_sum), money(p_total),
                   money(o_sum) == money(p_total), src,
                   " + ".join(money(s) for s in p_sums) if table.split else "")

    key = ", ".join(table.key)
    o_keys = {tuple(estate.canon(v) for v in r) for r in ora_rows(ora, f"SELECT {key} FROM {name}")}
    p_key_lists = [[tuple(estate.canon(v) for v in r) for r in pg.execute(f"SELECT {key} FROM {t}")]
                   for t in targets]
    p_keys: set = set()
    overlap = 0
    for keys in p_key_lists:
        overlap += len(p_keys.intersection(keys))
        p_keys.update(keys)
    missing = len(o_keys - p_keys)
    extra = len(p_keys - o_keys)
    report.add(name, f"key_coverage({key})", len(o_keys), len(o_keys & p_keys),
               missing == 0 and extra == 0 and overlap == 0, src,
               f"missing={missing} extra={extra}"
               + (f" in-both-tables={overlap}" if table.split else ""))

    col_list = ", ".join(names)
    o_ck = checksum_rows(ora_rows(ora, f"SELECT {col_list} FROM {name}"))
    p_ck = checksum_rows(pg.execute(f"SELECT {col_list} FROM {targets[0]}"))
    for t in targets[1:]:
        p_ck = p_ck.merge(checksum_rows(pg.execute(f"SELECT {col_list} FROM {t}")))
    report.add(name, "row_checksum(all columns)", o_ck.hexdigest(), p_ck.hexdigest(),
               o_ck.hexdigest() == p_ck.hexdigest() and o_ck.count == p_ck.count, src,
               "order-independent md5 over every column of every row"
               + (" (orphan rows without quarantine_reason)" if table.split else ""))


def orphan_checks(report: Report, ora, pg) -> None:
    name = estate.ORPHAN_TABLE
    src = f"{ORACLE}.INVOICE_LINE (no matching INVOICE_HEADER)"
    where = "WHERE NOT EXISTS (SELECT 1 FROM invoice_header h WHERE h.invoice_id = l.invoice_id)"
    o_count, o_amt, o_tax = ora_one(
        ora, f"SELECT COUNT(*), SUM(amount), SUM(tax_amt) FROM invoice_line l {where}")
    p_count, p_amt, p_tax = pg_one(pg, f"SELECT count(*), sum(amount), sum(tax_amt) FROM {name}")
    report.add(name, "row_count", o_count, p_count, o_count == p_count, src)
    report.add(name, "sum(amount)", money(o_amt), money(p_amt), money(o_amt) == money(p_amt), src)
    report.add(name, "sum(tax_amt)", money(o_tax), money(p_tax), money(o_tax) == money(p_tax), src)
    o_ids = {r[0] for r in ora_rows(ora, f"SELECT line_id FROM invoice_line l {where}")}
    p_ids = {r[0] for r in pg.execute(f"SELECT line_id FROM {name}")}
    report.add(name, "key_coverage(line_id)", len(o_ids), len(o_ids & p_ids), o_ids == p_ids, src,
               f"missing={len(o_ids - p_ids)} extra={len(p_ids - o_ids)}")
    reasons = pg.execute(
        f"SELECT quarantine_reason, count(*) FROM {name} GROUP BY 1 ORDER BY 1").fetchall()
    unreasoned = pg_one(pg, f"SELECT count(*) FROM {name} WHERE quarantine_reason IS NULL"
                            " OR quarantine_reason = ''")[0]
    report.add(name, "quarantine_reason populated", o_count, p_count - unreasoned,
               unreasoned == 0, "migration rule: every quarantined row carries a reason",
               "; ".join(f"{r} x{c}" for r, c in reasons))
    valid = ora_one(ora, "SELECT COUNT(*), SUM(amount), SUM(tax_amt) FROM invoice_line l WHERE"
                         " EXISTS (SELECT 1 FROM invoice_header h WHERE h.invoice_id = l.invoice_id)")
    p_valid = pg_one(pg, "SELECT count(*), sum(amount), sum(tax_amt) FROM invoice_line")
    report.add("invoice_line", "valid rows (with header)", valid[0], p_valid[0],
               valid[0] == p_valid[0], f"{ORACLE}.INVOICE_LINE joined to INVOICE_HEADER")
    report.add("invoice_line", "valid sum(amount)", money(valid[1]), money(p_valid[1]),
               money(valid[1]) == money(p_valid[1]), f"{ORACLE}.INVOICE_LINE joined to INVOICE_HEADER")
    report.add("invoice_line", "valid sum(tax_amt)", money(valid[2]), money(p_valid[2]),
               money(valid[2]) == money(p_valid[2]), f"{ORACLE}.INVOICE_LINE joined to INVOICE_HEADER")


def reference_checks(report: Report, ora, pg) -> None:
    """Coverage of every FK and every unenforced logical reference."""
    fks = pg.execute(
        """SELECT c.conname, cl.relname, a.attname, pcl.relname, pa.attname
             FROM pg_constraint c
             JOIN pg_class cl ON cl.oid = c.conrelid
             JOIN pg_namespace n ON n.oid = cl.relnamespace
             JOIN pg_class pcl ON pcl.oid = c.confrelid
             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             JOIN pg_attribute pa ON pa.attrelid = c.confrelid AND pa.attnum = c.confkey[1]
            WHERE c.contype = 'f' AND n.nspname = 'ow_billing'
            ORDER BY cl.relname, c.conname""").fetchall()
    refs = [(child, col, parent, pcol, None, conname) for conname, child, col, parent, pcol in fks]
    declared = {(r[0], r[1]) for r in refs}
    refs += [(c, col, p, pcol, f, None) for c, col, p, pcol, f in estate.LOGICAL_REFS
             if (c, col) not in declared]
    for child, col, parent, pcol, filt, conname in refs:
        extra = f" AND c.{filt}" if filt else ""

        def coverage_sql(table: str) -> str:
            return (f"SELECT COUNT(*), COUNT(p.{pcol}) FROM {table} c LEFT JOIN {parent} p"
                    f" ON p.{pcol} = c.{col} WHERE c.{col} IS NOT NULL{extra}")

        o_total, o_cov = ora_one(ora, coverage_sql(child))
        p_total, p_cov = pg_one(pg, coverage_sql(child))
        if child == "invoice_line" and col != "invoice_id":
            # Quarantined rows still reference customers: count both tables.
            q_total, q_cov = pg_one(pg, coverage_sql(estate.ORPHAN_TABLE))
            p_total, p_cov = p_total + q_total, p_cov + q_cov
        kind = f"FK {conname}" if conname else "logical ref (not enforced)"
        check = f"ref_coverage({col} -> {parent}.{pcol})"
        detail = f"{kind}; oracle {o_cov}/{o_total} covered, postgres {p_cov}/{p_total}"
        if child == "invoice_line" and col != "invoice_id":
            detail += f" (invoice_line + {estate.ORPHAN_TABLE})"
        if child == "invoice_line" and col == "invoice_id":
            orphan_total, orphan_cov = pg_one(
                pg, f"SELECT count(*), count(p.{pcol}) FROM {estate.ORPHAN_TABLE} c"
                    f" LEFT JOIN {parent} p ON p.{pcol} = c.{col}")
            detail += (f"; {estate.ORPHAN_TABLE} {orphan_cov}/{orphan_total} covered"
                       " (quarantined because uncovered)")
            ok = p_cov == p_total == o_cov and orphan_cov == 0 and orphan_total == o_total - o_cov
            report.add(child, check, f"{o_cov} covered + {o_total - o_cov} uncovered",
                       f"{p_cov} in invoice_line + {orphan_total} in {estate.ORPHAN_TABLE}",
                       ok, f"{ORACLE}.{child.upper()}", detail)
            continue
        ok = (o_total, o_cov) == (p_total, p_cov)
        report.add(child, check, f"{o_cov}/{o_total}", f"{p_cov}/{p_total}", ok,
                   f"{ORACLE}.{child.upper()}", detail)


def sequence_checks(report: Report, ora, pg) -> None:
    oracle_next = {n: int(v) for n, v in ora_rows(
        ora, "SELECT LOWER(sequence_name), last_number FROM user_sequences")}
    for seq in estate.SEQUENCES:
        last, called = pg_one(pg, f"SELECT last_value, is_called FROM {seq}")
        nxt = last + 1 if called else last
        report.add(seq, "next_value", oracle_next[seq], nxt, nxt >= oracle_next[seq],
                   f"{ORACLE} USER_SEQUENCES.LAST_NUMBER")


def constraint_checks(report: Report, ora, pg) -> None:
    o_cons = {r[0] for r in ora_rows(
        ora, "SELECT LOWER(constraint_name) FROM user_constraints"
             " WHERE constraint_type IN ('P', 'U', 'R', 'C')"
             " AND constraint_name NOT LIKE 'SYS\\_%' ESCAPE '\\'"
             " AND table_name NOT LIKE 'BIN$%'")}
    p_cons = {r[0] for r in pg.execute(
        "SELECT conname FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace"
        " WHERE n.nspname = 'ow_billing' AND contype IN ('p', 'u', 'f', 'c')")}
    missing = sorted(o_cons - p_cons)
    added = sorted(p_cons - o_cons)
    report.add("(schema)", "named constraints carried over", len(o_cons), len(o_cons & p_cons),
               not missing, f"{ORACLE} USER_CONSTRAINTS",
               f"missing={missing or 'none'}; added in Postgres={added or 'none'}")


def seed_checks(report: Report, ora, pg, ns: str) -> dict:
    manifest_path = MANIFESTS / f"{ns}.json"
    manifest = json.loads(manifest_path.read_text())
    targets = manifest["targets"]
    src = f"manifest:testdata/legacy/manifests/{ns}.json"
    batch = batch_no(ns)

    def seed_ck(sql, params):
        import hashlib
        h = hashlib.md5()
        for pk, amt in sorted((r[0], f"{r[1]:.2f}") for r in pg.execute(sql, params)):
            h.update(f"{pk}:{amt}\n".encode())
        return h.hexdigest()

    ns_counts = {
        "customer_master": pg_one(pg, "SELECT count(*) FROM customer_master"
                                      " WHERE conversion_batch_no = %s", (batch,))[0],
        "entity_attr_value": pg_one(pg, "SELECT count(*) FROM entity_attr_value e JOIN"
                                        " customer_master c ON c.cust_id = e.entity_id"
                                        " WHERE c.conversion_batch_no = %s", (batch,))[0],
        "invoice_header": pg_one(pg, "SELECT count(*) FROM invoice_header WHERE batch_no = %s",
                                 (batch,))[0],
        "invoice_line": pg_one(pg, "SELECT (SELECT count(*) FROM invoice_line WHERE batch_no = %s)"
                                   " + (SELECT count(*) FROM invoice_line_orphan WHERE batch_no = %s)",
                               (batch, batch))[0],
        "tenants": pg_one(pg, "SELECT count(*) FROM tenants WHERE starts_with(name, %s)",
                          (f"{ns}::",))[0],
    }
    for table, actual in ns_counts.items():
        key = f"oracle.OW_BILLING.{table.upper()}"
        if key in targets:
            expected = targets[key]["rows"]
            report.add(table, f"seed rows (ns={ns})", expected, actual, expected == actual, src)
    cust_ck = seed_ck("SELECT cust_id, cur_bal_amt FROM customer_master"
                      " WHERE conversion_batch_no = %s", (batch,))
    exp = targets["oracle.OW_BILLING.CUSTOMER_MASTER"]["checksum"]
    report.add("customer_master", f"seed checksum(cust_id, cur_bal_amt) (ns={ns})", exp, cust_ck,
               exp == cust_ck, src)
    line_ck = seed_ck("SELECT line_id, amount FROM invoice_line WHERE batch_no = %s UNION ALL"
                      " SELECT line_id, amount FROM invoice_line_orphan WHERE batch_no = %s",
                      (batch, batch))
    exp = targets["oracle.OW_BILLING.INVOICE_LINE"]["checksum"]
    report.add("invoice_line", f"seed checksum(line_id, amount) (ns={ns})", exp, line_ck,
               exp == line_ck, src, "over invoice_line + invoice_line_orphan")

    detected = {
        ("orphaned_rows", "oracle.OW_BILLING.INVOICE_LINE"): pg_one(
            pg, "SELECT count(*) FROM invoice_line_orphan WHERE batch_no = %s", (batch,))[0],
        ("dirty_dates", "oracle.OW_BILLING.CUSTOMER_MASTER.SIGNUP_DT"): pg_one(
            pg, DIRTY_DATE_SQL["postgres"], (batch,))[0],
        ("malformed_csv_lists", "oracle.OW_BILLING.CUSTOMER_MASTER.RELATED_ACCT_IDS"): pg_one(
            pg, BAD_CSV_SQL["postgres"], (batch,))[0],
    }
    oracle_detected = {
        "orphaned_rows": ora_one(
            ora, "SELECT COUNT(*) FROM invoice_line l WHERE batch_no = :1 AND NOT EXISTS"
                 " (SELECT 1 FROM invoice_header h WHERE h.invoice_id = l.invoice_id)", (batch,))[0],
        "dirty_dates": ora_one(ora, DIRTY_DATE_SQL["oracle"], (batch,))[0],
        "malformed_csv_lists": ora_one(ora, BAD_CSV_SQL["oracle"], (batch,))[0],
    }
    for (kind, target), count in detected.items():
        report.add(target.split(".")[2].lower(), f"anomaly {kind} (ns={ns})",
                   oracle_detected[kind], count, oracle_detected[kind] == count,
                   f"{ORACLE} (same detector)", target)
    expected_set = sorted(f"{a['kind']}:{a['target']}:{a['count']}"
                          for a in manifest.get("planted_anomalies", []))
    actual_set = sorted(f"{k}:{t}:{c}" for (k, t), c in detected.items())
    return {
        "expected_set": expected_set,
        "actual_set": actual_set,
        "missing": sorted(set(expected_set) - set(actual_set)),
        "unexpected": sorted(set(actual_set) - set(expected_set)),
    }


UNVERIFIED = [
    "pkg_ow_util.log_msg: Oracle wrote BILLING_AUDIT_LOG in an autonomous transaction; "
    "on Postgres the log row commits or rolls back with the caller. Only the commit path "
    "is exercised by the parity run.",
    "pkg_jobs.job_nightly_dunning / job_purge_audit_log: the DBMS_SCHEDULER jobs were "
    "created DISABLED in Oracle and never ran; the Postgres procedure bodies exist but no "
    "scheduler is wired and they were not executed.",
    "Concurrent writers: Oracle row-lock behaviour (SELECT ... FOR UPDATE in "
    "sp_change_plan) is ported but not exercised under concurrency.",
    "Scales other than demo (SCALE=ci/full) were not migrated or reconciled.",
]


def to_markdown(doc: dict) -> str:
    lines = [
        f"# Reconciliation: {doc['unit']} (ns={doc['namespace']})",
        "",
        f"Generated {doc['generated_at']}, run mode `{doc['run_mode']}`. Expected values are "
        "read live from Oracle `OW_BILLING` (FREEPDB1) or the seed manifest; actual values "
        "are recomputed from the PostgreSQL 15 target `ow_tp_billing.ow_billing`.",
        "",
        f"**Result: {doc['summary']['passed']}/{doc['summary']['total']} checks pass.**",
        "",
        "| Table | Check | Oracle (expected) | Postgres (actual) | Result | Detail |",
        "|---|---|---|---|---|---|",
    ]
    for c in doc["checks"]:
        detail = str(c.get("detail", "")).replace("|", "\\|")
        lines.append(f"| `{c['table']}` | {c['check']} | {c['expected']} | {c['actual']} "
                     f"| {c['result']} | {detail} |")
    rerun = doc["idempotency_rerun"]
    anomalies = doc["planted_anomaly_detections"]
    lines += [
        "",
        f"**Idempotency rerun:** {rerun['result']}. {rerun['evidence']}",
        "",
        "**Planted anomalies** (manifest vs detected on Postgres): "
        f"expected {anomalies['expected_set']}, detected {anomalies['actual_set']}, "
        f"missing {anomalies['missing'] or 'none'}, unexpected {anomalies['unexpected'] or 'none'}.",
        "",
        "**Unverified paths:**",
        "",
    ]
    lines += [f"- {p}" for p in doc["unverified_paths"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ns", default="demo")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    try:
        rerun = idempotency_rerun()
    except migrate.TargetDiverged as exc:
        print(f"[recon] refused, no report written: {exc}", file=sys.stderr)
        return 2
    report = Report()
    with estate.oracle_connect() as ora, estate.pg_connect() as pg:
        for table in estate.TABLES:
            table_checks(report, ora, pg, table)
        orphan_checks(report, ora, pg)
        reference_checks(report, ora, pg)
        sequence_checks(report, ora, pg)
        constraint_checks(report, ora, pg)
        anomalies = seed_checks(report, ora, pg, args.ns)

    passed = sum(c["result"] == "pass" for c in report.checks)
    doc = {
        "kind": "recon-report",
        "unit": UNIT,
        "namespace": args.ns,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_mode": "live",
        "summary": {"total": len(report.checks), "passed": passed,
                    "failed": len(report.checks) - passed},
        "checks": report.checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": rerun,
        "planted_anomaly_detections": anomalies,
        "unverified_paths": UNVERIFIED,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.out_dir / f"{UNIT}.{args.ns}"
    Path(f"{stem}.recon.json").write_text(json.dumps(doc, indent=2, default=str) + "\n")
    Path(f"{stem}.md").write_text(to_markdown(doc))
    print(f"[recon] {passed}/{len(report.checks)} checks pass; idempotency {rerun['result']}")
    for c in report.checks:
        if c["result"] != "pass":
            print(f"[recon] FAIL {c['id']}: expected={c['expected']} actual={c['actual']} {c.get('detail', '')}")
    print(f"[recon] wrote {stem}.recon.json and {stem}.md")
    ok = passed == len(report.checks) and rerun["result"] == "pass" and not anomalies["missing"] \
        and not anomalies["unexpected"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
