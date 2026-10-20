"""Seeds the claims schema from the forty claims hub input messages and the Commission Pay policies.

Inputs only: the FNOL messages and their policy inquiry stubs, the payment instructions, the assignment
requests and their roster stubs. The hub's outputs (Saxon goldens) are what parity/parity.py checks this
against, so nothing here reads corpus/golden except the triage outcome, which is the rules engine's answer
and is owned by the claims-hub-camel conversion, not by this model.
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

import psycopg

from common import corpus_dir, half_even, half_up, money, pg_dsn, read_xml, text

POLICY_STATUS = {"Active": "IN_FORCE", "Lapsed": "LAPSED", "Cancelled": "CANCELLED"}
RESERVE_FACTOR = {"COLL": "1.10", "COMP": "1.00", "GLAS": "0.85", "THFT": "1.25", "FIRE": "1.40",
                  "WATR": "1.30", "WIND": "1.15", "LIAB": "1.60"}
INJURY_LOADING = Decimal("0.35")
SLA_DAYS = {"HIGH": 1, "MED": 3, "LOW": 7}


def day(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def flag(value: str | None) -> bool:
    return value == "true"


def mask_tax_id(tax_id: str) -> str:
    return "***-**-" + tax_id.replace("-", "")[-4:]


def load_commission_side(cur) -> None:
    cur.execute("""
        INSERT INTO claims.policyholders (policyholder_id, source_system, full_name, tax_id_masked)
        SELECT 'CP-' || lpad(policy_id::text, 6, '0'), 'COMMISSION_PAY', holder_name, NULL
          FROM commission.policies
    """)
    cur.execute("""
        INSERT INTO claims.policies (policy_no, source_system, policyholder_id, line_of_business, product_code,
                                     status, effective_date, expiration_date, annual_premium, deductible,
                                     coverage_limit)
        SELECT po.policy_no, 'COMMISSION_PAY', 'CP-' || lpad(po.policy_id::text, 6, '0'), pr.line_of_business,
               po.product_code, po.status, po.issued_date, NULL, po.annual_premium, NULL, NULL
          FROM commission.policies po
          JOIN commission.products pr ON pr.product_code = po.product_code
    """)


def load_claims(cur, corpus) -> None:
    for path in sorted((corpus / "inputs" / "fnol").glob("*.xml")):
        msg = read_xml(path).find("ClaimsNotificationAddRq")
        occ = msg.find("ClaimsOccurrence")
        insured = msg.find("InsuredOrPrincipal")
        claim_no = text(occ, "ClaimNumber")
        policy_no = text(msg, "Policy/PolicyNumber")
        pol = read_xml(corpus / "stubs" / "policy" / f"{policy_no}.xml")
        party = text(pol, "InsuredPartyId")
        name = f"{text(insured, 'GivenName')} {text(insured, 'Surname')}"
        cur.execute(
            "INSERT INTO claims.policyholders VALUES (%s, 'CLAIMS_HUB', %s, %s) ON CONFLICT DO NOTHING",
            (party, name, mask_tax_id(text(insured, "TaxId"))))
        effective, expiration = day(text(pol, "EffectiveDt")), day(text(pol, "ExpirationDt"))
        deductible, limit = money(pol, "DeductibleAmt"), money(pol, "CoverageLimitAmt")
        cur.execute(
            """INSERT INTO claims.policies (policy_no, source_system, policyholder_id, line_of_business,
                                            product_code, status, effective_date, expiration_date,
                                            annual_premium, deductible, coverage_limit)
               VALUES (%s, 'CLAIMS_HUB', %s, %s, NULL, %s, %s, %s, NULL, %s, %s) ON CONFLICT DO NOTHING""",
            (policy_no, party, text(pol, "LOBCd"), POLICY_STATUS[text(pol, "PolicyStatusCd")], effective,
             expiration, deductible, limit))

        loss, reported = day(text(occ, "LossDt")), day(text(occ, "ReportedDt"))
        cause = text(occ, "LossCauseCd")
        injury = flag(text(occ, "InjuryInd"))
        estimate = half_even(money(occ, "EstimatedLossAmt"))
        net_exposure = max(min(estimate, limit) - deductible, Decimal("0.00"))
        factor = Decimal(RESERVE_FACTOR.get(cause, "1.00")) + (INJURY_LOADING if injury else Decimal("0"))
        reserve = half_even(estimate * factor)
        in_force = text(pol, "PolicyStatusCd") == "Active" and effective <= loss <= expiration
        triage = json.loads((corpus / "golden" / "triage" / f"{claim_no}.json").read_text())["Outcome"]
        cur.execute(
            "INSERT INTO claims.claims VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s, %s)",
            (claim_no, policy_no, party, text(msg, "Producer/ProducerId"), text(msg, "Policy/LOBCd"), cause, loss,
             reported, (reported - loss).days, (loss - effective).days, injury, flag(text(occ, "PoliceReportInd")),
             flag(text(insured, "PriorFraudFlagInd")), in_force, estimate, net_exposure, reserve, triage,
             triage != "DECLINE_NOT_IN_FORCE"))


def load_payments(cur, corpus) -> None:
    for path in sorted((corpus / "inputs" / "payment").glob("*.xml")):
        pi = read_xml(path)
        lines = [(text(ln, "LineType"), Decimal(text(ln, "Amount"))) for ln in pi.findall("Line")]
        by_type = {t: sum((a for lt, a in lines if lt == t), Decimal("0")) for t in ("IND", "EXP", "SLV")}
        indemnity, expense = half_even(by_type["IND"]), half_even(by_type["EXP"])
        salvage = half_even(-by_type["SLV"])
        net = half_even(by_type["IND"] + by_type["EXP"] + by_type["SLV"])
        debit = sum((half_up(abs(a)) for _, a in lines if a >= 0), Decimal("0.00"))
        credit = sum((half_up(abs(a)) for _, a in lines if a < 0), Decimal("0.00"))
        cur.execute(
            "INSERT INTO claims.claim_payments VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (text(pi, "InstructionId"), text(pi, "ClaimNumber"), text(pi, "PolicyNumber"), text(pi, "VendorCode"),
             text(pi, "Payee/Name"), text(pi, "Payee/PayeeType"), day(text(pi, "ValueDate")), text(pi, "CurrencyCd"),
             len(lines), indemnity, expense, salvage, net, debit, credit))


def load_assignments(cur, corpus) -> None:
    for path in sorted((corpus / "inputs" / "assignment").glob("*.xml")):
        req = read_xml(path)
        request_id = text(req, "RequestId")
        region, skill = text(req, "Region"), text(req, "RequiredSkill")
        roster = read_xml(corpus / "stubs" / "roster" / f"{request_id}.xml")
        eligible = [
            (int(text(a, "OpenClaims")), text(a, "AdjusterId"), text(a, "Name"), text(a, "Email"))
            for a in roster.findall("Adjuster")
            if text(a, "Available") == "true" and text(a, "Region") == region
            and skill in text(a, "Skills").split(",") and int(text(a, "OpenClaims")) < int(text(a, "MaxClaims"))
        ]
        chosen = min(eligible) if eligible else (None, None, None, None)
        severity = text(req, "Severity")
        requested = day(text(req, "RequestedDt"))
        cur.execute(
            "INSERT INTO claims.adjuster_assignments VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s)",
            (request_id, text(req, "ClaimNumber"), text(req, "LineOfBusiness"), text(req, "LossCause"), region,
             severity, skill, requested, half_even(money(req, "EstimatedAmount")), chosen[1], chosen[2], chosen[3],
             SLA_DAYS[severity], requested + dt.timedelta(days=SLA_DAYS[severity]), not eligible))


def main() -> None:
    corpus = corpus_dir()
    with psycopg.connect(pg_dsn()) as pg, pg.cursor() as cur:
        load_commission_side(cur)
        load_claims(cur, corpus)
        load_payments(cur, corpus)
        load_assignments(cur, corpus)
        for table in ("policyholders", "policies", "claims", "claim_payments", "adjuster_assignments"):
            cur.execute(f"SELECT count(*) FROM claims.{table}")
            print(f"claims.{table}: {cur.fetchone()[0]} rows")


if __name__ == "__main__":
    main()
