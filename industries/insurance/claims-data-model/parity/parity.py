"""Parity gate: every table, its rows and the sums of its money columns, source against target.

Source is the legacy side, read directly: Oracle COMMISSION_PAY / COMMISSION_DW for commissions, the claims
hub corpus for claims (the forty input messages and the Saxon goldens the hub's maps wrote from them).
Target is PostgreSQL (the claims and commission schemas and the dbt marts). Checked to the cent, no band.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import psycopg
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "loader"))
from common import corpus_dir, oracle_connect, pg_dsn, read_xml, text  # noqa: E402

ACCEPTED = Path(__file__).resolve().parent / "accepted_differences.yaml"
UNEXPLAINED = "UNEXPLAINED: question for the owner"


def ora_scalar(ora, sql, **binds):
    with ora.cursor() as cur:
        cur.execute(sql, binds)
        return cur.fetchone()


def pg_scalar(pg, sql):
    with pg.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


def dec(v) -> Decimal:
    return Decimal(v if v is not None else 0)


def corpus_measures(corpus: Path) -> dict:
    fnol = sorted((corpus / "inputs" / "fnol").glob("*.xml"))
    stubs = sorted((corpus / "stubs" / "policy").glob("*.xml"))
    payments = sorted((corpus / "inputs" / "payment").glob("*.xml"))
    requests = sorted((corpus / "inputs" / "assignment").glob("*.xml"))
    insert = [read_xml(p) for p in sorted((corpus / "golden" / "insert-claim").glob("*.xml"))]
    facts = [read_xml(p) for p in sorted((corpus / "golden" / "triage-facts").glob("*.xml"))]
    ledger = [read_xml(p) for p in sorted((corpus / "golden" / "ledger-post").glob("*.xml"))]
    notices = [read_xml(p) for p in sorted((corpus / "golden" / "assignment-notice").glob("*.xml"))]
    triage = [json.loads(p.read_text()) for p in sorted((corpus / "golden" / "triage").glob("*.json"))]
    trailers = []
    vendor_net_by_instruction = {}
    for p in sorted((corpus / "golden" / "vendor-remittance-ff").glob("*.txt")):
        trl = [ln for ln in p.read_text().splitlines() if ln.startswith("TRL")][0]
        # Trailer per Schemas/PaymentVendor_Remittance_FF.xsd: TRL, PaymentCount(6) at 3, DebitTotalCents(14) at 9,
        # CreditTotalCents(14) at 23, HashTotal(10) at 37.
        trailers.append((int(trl[3:9]), Decimal(int(trl[9:23])) / 100, Decimal(int(trl[23:37])) / 100))
        vendor_net_by_instruction[p.stem] = trailers[-1][1] - trailers[-1][2]
    ledger_net_by_instruction = {p.stem: Decimal(text(read_xml(p), "NetAmount"))
                                 for p in sorted((corpus / "golden" / "ledger-post").glob("*.xml"))}
    gap_by_instruction = {k: vendor_net_by_instruction[k] - ledger_net_by_instruction[k]
                          for k in ledger_net_by_instruction}
    stub_docs = [read_xml(p) for p in stubs]
    m = {
        "fnol_messages": len(fnol),
        "policy_stubs": len(stub_docs),
        "insured_parties": len({text(s, "InsuredPartyId") for s in stub_docs}),
        "stub_deductible": sum(Decimal(text(s, "DeductibleAmt")) for s in stub_docs),
        "stub_limit": sum(Decimal(text(s, "CoverageLimitAmt")) for s in stub_docs),
        "fnol_estimate": sum(Decimal(text(read_xml(p), "ClaimsNotificationAddRq/ClaimsOccurrence/EstimatedLossAmt"))
                             for p in fnol),
        "claims_inserted": sum(1 for t in triage if t["Outcome"] != "DECLINE_NOT_IN_FORCE"),
        "net_exposure": sum(Decimal(text(d, "NetExposure")) for d in insert),
        "reserve": sum(Decimal(text(d, "ReserveEstimate")) for d in facts),
        "payment_instructions": len(payments),
        "ledger_posts": len(ledger),
        "ledger_lines": sum(int(text(d, "LineCount")) for d in ledger),
        "ledger_indemnity": sum(Decimal(text(d, "IndemnityAmount")) for d in ledger),
        "ledger_expense": sum(Decimal(text(d, "ExpenseAmount")) for d in ledger),
        "ledger_salvage": sum(Decimal(text(d, "SalvageCredit")) for d in ledger),
        "ledger_net": sum(Decimal(text(d, "NetAmount")) for d in ledger),
        "vendor_debit": sum(t[1] for t in trailers),
        "vendor_credit": sum(t[2] for t in trailers),
        "vendor_net": sum(t[1] - t[2] for t in trailers),
        "gap_by_instruction": gap_by_instruction,
        "assignment_requests": len(requests),
        "notices_escalated": sum(1 for n in notices if text(n, "Escalated") == "true"),
        "notice_pairs": sorted((text(n, "ClaimNumber"), text(n, "AdjusterId")) for n in notices),
        "request_estimate": sum(Decimal(text(read_xml(p), "EstimatedAmount")) for p in requests),
        "payment_months": sorted({text(read_xml(p), "ValueDate")[:7] for p in payments}),
        "loss_months": sorted({text(read_xml(p), "ClaimsNotificationAddRq/ClaimsOccurrence/LossDt")[:7]
                               for p in fnol}),
    }
    return m


def build_checks(ora, dw, pg, c: dict, accepted: dict) -> list[dict]:
    checks: list[dict] = []

    def add(table, measure, kind, source_label, source_value, target_sql):
        target_value = pg_scalar(pg, target_sql)[0]
        checks.append({"table": table, "measure": measure, "kind": kind, "source": source_label,
                       "source_value": dec(source_value), "target_value": dec(target_value)})

    def ora_q(sql, **b):
        return ora_scalar(ora, sql, **b)[0]

    # Commission Pay (Oracle COMMISSION_PAY) -> commission schema
    for table in ("agents", "products", "commission_rates", "commission_splits"):
        add(f"commission.{table}", "rows", "rows", f"Oracle COMMISSION_PAY.{table.upper()}",
            ora_q(f"SELECT COUNT(*) FROM {table}"), f"SELECT count(*) FROM commission.{table}")
    add("commission.policies", "rows", "rows", "Oracle COMMISSION_PAY.POLICIES",
        ora_q("SELECT COUNT(*) FROM policies"), "SELECT count(*) FROM commission.policies")
    add("commission.policies", "sum(annual_premium)", "money", "Oracle COMMISSION_PAY.POLICIES",
        ora_q("SELECT SUM(annual_premium) FROM policies"), "SELECT sum(annual_premium) FROM commission.policies")
    add("commission.commission_ledger", "rows", "rows", "Oracle COMMISSION_PAY.COMMISSION_LEDGER",
        ora_q("SELECT COUNT(*) FROM commission_ledger"), "SELECT count(*) FROM commission.commission_ledger")
    for col in ("base_premium", "commission_amt"):
        add("commission.commission_ledger", f"sum({col})", "money", "Oracle COMMISSION_PAY.COMMISSION_LEDGER",
            ora_q(f"SELECT SUM({col}) FROM commission_ledger"),
            f"SELECT sum({col}) FROM commission.commission_ledger")

    # Claims and policy model (corpus + Commission Pay) -> claims schema
    cp_policies = ora_q("SELECT COUNT(*) FROM policies")
    add("claims.policyholders", "rows", "rows", "Oracle POLICIES holders + corpus distinct InsuredPartyId",
        cp_policies + c["insured_parties"], "SELECT count(*) FROM claims.policyholders")
    add("claims.policies", "rows", "rows", "Oracle POLICIES + corpus stubs/policy",
        cp_policies + c["policy_stubs"], "SELECT count(*) FROM claims.policies")
    add("claims.policies", "sum(annual_premium)", "money", "Oracle COMMISSION_PAY.POLICIES",
        ora_q("SELECT SUM(annual_premium) FROM policies"), "SELECT sum(annual_premium) FROM claims.policies")
    add("claims.policies", "sum(deductible)", "money", "corpus stubs/policy DeductibleAmt",
        c["stub_deductible"], "SELECT sum(deductible) FROM claims.policies")
    add("claims.policies", "sum(coverage_limit)", "money", "corpus stubs/policy CoverageLimitAmt",
        c["stub_limit"], "SELECT sum(coverage_limit) FROM claims.policies")
    add("claims.claims", "rows", "rows", "corpus inputs/fnol messages",
        c["fnol_messages"], "SELECT count(*) FROM claims.claims")
    add("claims.claims", "rows entered_claims_system", "rows", "corpus golden/triage, outcome not DECLINE",
        c["claims_inserted"], "SELECT count(*) FROM claims.claims WHERE entered_claims_system")
    add("claims.claims", "sum(estimated_amount)", "money", "corpus inputs/fnol EstimatedLossAmt",
        c["fnol_estimate"], "SELECT sum(estimated_amount) FROM claims.claims")
    add("claims.claims", "sum(net_exposure)", "money", "corpus golden/insert-claim NetExposure",
        c["net_exposure"], "SELECT sum(net_exposure) FROM claims.claims")
    add("claims.claims", "sum(reserve_estimate)", "money", "corpus golden/triage-facts ReserveEstimate",
        c["reserve"], "SELECT sum(reserve_estimate) FROM claims.claims")
    add("claims.claim_payments", "rows", "rows", "corpus golden/ledger-post documents",
        c["ledger_posts"], "SELECT count(*) FROM claims.claim_payments")
    add("claims.claim_payments", "sum(line_count)", "rows", "corpus golden/ledger-post LineCount",
        c["ledger_lines"], "SELECT sum(line_count) FROM claims.claim_payments")
    for col, key in (("indemnity_amount", "ledger_indemnity"), ("expense_amount", "ledger_expense"),
                     ("salvage_credit", "ledger_salvage"), ("net_amount", "ledger_net")):
        add("claims.claim_payments", f"sum({col})", "money", "corpus golden/ledger-post", c[key],
            f"SELECT sum({col}) FROM claims.claim_payments")
    add("claims.claim_payments", "sum(vendor_debit_total)", "money", "corpus golden/vendor-remittance-ff TRL debit",
        c["vendor_debit"], "SELECT sum(vendor_debit_total) FROM claims.claim_payments")
    add("claims.claim_payments", "sum(vendor_credit_total)", "money",
        "corpus golden/vendor-remittance-ff TRL credit", c["vendor_credit"],
        "SELECT sum(vendor_credit_total) FROM claims.claim_payments")
    checks.append({"table": "claims.claim_payments", "measure": "net_amount_vs_vendor_file", "kind": "money",
                   "source": "corpus golden/vendor-remittance-ff TRL debit - credit",
                   "source_value": c["vendor_net"],
                   "target_value": dec(pg_scalar(pg, "SELECT sum(net_amount) FROM claims.claim_payments")[0])})
    add("claims.claim_payments", "gap_equals_vendor_rounding_difference", "money",
        "corpus golden vendor-remittance-ff net - golden ledger-post NetAmount",
        sum(c["gap_by_instruction"].values()), "SELECT sum(vendor_rounding_difference) FROM claims.claim_payments")
    with pg.cursor() as cur:
        cur.execute("SELECT instruction_id, vendor_rounding_difference FROM claims.claim_payments")
        target_gap = dict(cur.fetchall())
    keys = set(target_gap) | set(c["gap_by_instruction"])
    checks.append({"table": "claims.claim_payments", "measure": "rows whose vendor_rounding_difference differs from the golden gap",
                   "kind": "rows", "source": "corpus golden vendor-remittance-ff, ledger-post per instruction",
                   "source_value": Decimal(0),
                   "target_value": Decimal(sum(1 for k in keys if target_gap.get(k) != c["gap_by_instruction"].get(k)))})
    add("claims.adjuster_assignments", "rows", "rows", "corpus inputs/assignment requests",
        c["assignment_requests"], "SELECT count(*) FROM claims.adjuster_assignments")
    add("claims.adjuster_assignments", "rows escalated", "rows", "corpus golden/assignment-notice Escalated",
        c["notices_escalated"], "SELECT count(*) FROM claims.adjuster_assignments WHERE escalated")
    with pg.cursor() as cur:
        cur.execute("SELECT claim_number, coalesce(adjuster_id, 'UNASSIGNED') FROM claims.adjuster_assignments")
        target_pairs = sorted(cur.fetchall())
    checks.append({"table": "claims.adjuster_assignments", "measure": "rows whose adjuster differs from the notice",
                   "kind": "rows", "source": "corpus golden/assignment-notice AdjusterId",
                   "source_value": Decimal(0),
                   "target_value": Decimal(sum(1 for a, b in zip(c["notice_pairs"], target_pairs) if a != b))})
    add("claims.adjuster_assignments", "sum(estimated_amount)", "money", "corpus inputs/assignment EstimatedAmount",
        c["request_estimate"], "SELECT sum(estimated_amount) FROM claims.adjuster_assignments")

    # Marts against the legacy numbers they summarise
    mv = ora_scalar(dw, """SELECT COUNT(DISTINCT agent_code || '|' || period_month), SUM(total_commission)
                             FROM mv_agent_commission_summary""")
    add("marts.commission_by_agent_period", "rows", "rows",
        "Oracle COMMISSION_DW.MV_AGENT_COMMISSION_SUMMARY agent x period", mv[0],
        "SELECT count(*) FROM marts.commission_by_agent_period")
    add("marts.commission_by_agent_period", "sum(total_commission)", "money",
        "Oracle COMMISSION_DW.MV_AGENT_COMMISSION_SUMMARY", mv[1],
        "SELECT sum(total_commission) FROM marts.commission_by_agent_period")
    lo = min(ora_q("SELECT MIN(period_month) FROM commission_ledger"), c["payment_months"][0], c["loss_months"][0])
    hi = max(ora_q("SELECT MAX(period_month) FROM commission_ledger"), c["payment_months"][-1], c["loss_months"][-1])
    months = ora_q("SELECT MONTHS_BETWEEN(TO_DATE(:hi, 'YYYY-MM'), TO_DATE(:lo, 'YYYY-MM')) + 1 FROM dual",
                   hi=hi, lo=lo)
    lines = ora_q("SELECT COUNT(DISTINCT line_of_business) FROM products")
    add("marts.loss_ratio_by_product_period", "rows", "rows",
        f"Oracle PRODUCTS lines x months {lo}..{hi}", lines * months,
        "SELECT count(*) FROM marts.loss_ratio_by_product_period")
    earned = ora_q("""WITH m AS (SELECT TO_CHAR(ADD_MONTHS(TO_DATE(:lo, 'YYYY-MM'), LEVEL - 1), 'YYYY-MM') pm
                                   FROM dual CONNECT BY LEVEL <= :n)
                      SELECT SUM(ROUND(p.annual_premium / 12, 2)) FROM policies p
                        JOIN m ON m.pm >= TO_CHAR(p.issued_date, 'YYYY-MM') WHERE p.status = 'IN_FORCE'""",
                   lo=lo, n=int(months))
    add("marts.loss_ratio_by_product_period", "sum(earned_premium)", "money",
        "Oracle ROUND(annual_premium / 12, 2) per in-force policy-month", earned,
        "SELECT sum(earned_premium) FROM marts.loss_ratio_by_product_period")
    add("marts.loss_ratio_by_product_period", "sum(paid_loss)", "money", "corpus golden/ledger-post NetAmount",
        c["ledger_net"], "SELECT sum(paid_loss) FROM marts.loss_ratio_by_product_period")
    add("marts.loss_ratio_by_product_period", "sum(commission_paid)", "money",
        "Oracle COMMISSION_PAY.COMMISSION_LEDGER", ora_q("SELECT SUM(commission_amt) FROM commission_ledger"),
        "SELECT sum(commission_paid) FROM marts.loss_ratio_by_product_period")

    keys = [f"{chk['table']}.{chk['measure']}" for chk in checks]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise SystemExit(f"parity row keys must be unique, repeated: {', '.join(duplicates)}")
    for chk, key in zip(checks, keys):
        chk["difference"] = chk["target_value"] - chk["source_value"]
        chk["row"], chk["accepted"] = key, False
        if chk["difference"] == 0:
            chk["verdict"], chk["cause"] = "MATCH", ""
            continue
        chk["verdict"] = "RED"
        entry = accepted.get(key)
        if entry is None:
            chk["cause"] = UNEXPLAINED
        elif Decimal(str(entry["difference"])) != chk["difference"]:
            chk["cause"] = (f"{UNEXPLAINED}; accepted_differences.yaml records {entry['difference']} for this row, "
                            f"the difference is now {chk['difference']}")
        else:
            chk["accepted"] = True
            chk["cause"] = (f"{entry['reason']} Accepted {entry['decided_on']} "
                            f"(parity/accepted_differences.yaml): {entry['decision']}")
    return checks


def gate(checks: list[dict], accepted: dict) -> tuple[bool, str]:
    red = [c for c in checks if c["verdict"] == "RED"]
    unaccepted = [c["row"] for c in red if not c["accepted"]]
    stale = sorted(set(accepted) - {c["row"] for c in red})
    ok = not unaccepted and not stale
    line = (f"**Gate: {'PASS' if ok else 'FAIL'}.** {len(red)} RED row(s): {len(red) - len(unaccepted)} listed in "
            f"`parity/accepted_differences.yaml` with their reason, {len(unaccepted)} not listed"
            f"{' (' + ', '.join(unaccepted) + ')' if unaccepted else ''}; {len(stale)} accepted entr"
            f"{'y' if len(stale) == 1 else 'ies'} no longer RED{' (' + ', '.join(stale) + ')' if stale else ''}.")
    return ok, line


def fmt(v: Decimal, kind: str) -> str:
    return f"{v:,.0f}" if kind == "rows" else f"{v:,.2f}"


def render(checks: list[dict], corpus_ref: str, gate_line: str) -> str:
    out = [
        "| # | Table | Measure | Source | Source value | Target value | Difference | Verdict | Cause |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for i, c in enumerate(checks, 1):
        out.append(f"| {i} | `{c['table']}` | {c['measure']} | {c['source']} | {fmt(c['source_value'], c['kind'])} "
                   f"| {fmt(c['target_value'], c['kind'])} | {fmt(c['difference'], c['kind'])} | "
                   f"{'MATCH' if c['verdict'] == 'MATCH' else '**RED**'} | {c['cause']} |")
    for kind, label in (("rows", "Total, row checks"), ("money", "Total, money checks")):
        sel = [c for c in checks if c["kind"] == kind]
        s, t = sum(c["source_value"] for c in sel), sum(c["target_value"] for c in sel)
        red = sum(1 for c in sel if c["verdict"] == "RED")
        out.append(f"| | **{label}** | {len(sel)} checks | | **{fmt(s, kind)}** | **{fmt(t, kind)}** | "
                   f"**{fmt(t - s, kind)}** | **{len(sel) - red} MATCH, {red} RED** | |")
    red = sum(1 for c in checks if c["verdict"] == "RED")
    out.append(f"| | **Total** | {len(checks)} checks | | | | | **{len(checks) - red} MATCH, {red} RED** | |")
    header = (f"Parity: claims data model against the fixture (corpus at `{corpus_ref[:12]}`). "
              "Money to the cent, no tolerance.\n\n")
    return header + "\n".join(out) + "\n\n" + gate_line + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    corpus = corpus_dir()
    ref_file = corpus.parent / "REF"
    corpus_ref = ref_file.read_text().strip() if ref_file.exists() else os.environ.get("CORPUS_REF", "")
    c = corpus_measures(corpus)
    accepted = {e["row"]: e for e in (yaml.safe_load(ACCEPTED.read_text()) or [])}
    with oracle_connect() as ora, oracle_connect("commission_dw") as dw, psycopg.connect(pg_dsn()) as pg:
        checks = build_checks(ora, dw, pg, c, accepted)
    ok, gate_line = gate(checks, accepted)
    report = render(checks, corpus_ref, gate_line)
    Path(args.out).write_text(report)
    Path(args.out).with_suffix(".json").write_text(json.dumps(checks, default=str, indent=1) + "\n")
    print(report)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
