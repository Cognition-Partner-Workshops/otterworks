#!/usr/bin/env python3
"""Deterministic generator for the claims hub behaviour corpus.

Forty input messages across the three flows (16 FNOL, 14 payment instructions, 10 adjuster
assignment requests), the policy lookup and roster stubs the WCF-SQL ports would answer with,
and the two-part aggregate documents BizTalk feeds its multi-source maps. Re-running it
rewrites the same bytes; the golden outputs come from tools/xslt-golden over corpus/manifest.yaml.
"""
from __future__ import annotations

import os
import random
from datetime import date, timedelta
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
FNOL_NS = "http://schemas.thistlecombe.example/acord/claims/fnol"
POLICY_NS = "http://schemas.thistlecombe.example/acord/policy"
CLAIM_NS = "http://schemas.thistlecombe.example/canonical/claim"
PAY_NS = "http://schemas.thistlecombe.example/canonical/payment"
ASG_NS = "http://schemas.thistlecombe.example/claims/assignment"
AGG_NS = "http://schemas.microsoft.com/BizTalk/2003/aggschema"

AGENCIES = [("AG-0417", "Harbourline Brokers"), ("AG-0922", "Penrose & Daughters"), ("AG-1305", "Marlow Street Agency")]
CLAIMANTS = [
    ("Imogen", "Castellanos"), ("Rafael", "Oyelaran"), ("Hollis", "Brightwater"), ("Nadia", "Petrossian"),
    ("Tobias", "Whitcombe"), ("Priya", "Venkataraman"), ("Declan", "Ashworth"), ("Marisol", "Ibanez"),
    ("Everett", "Lindqvist"), ("Aiko", "Tanizaki"), ("Cormac", "Delahunty"), ("Yusra", "Haddad"),
    ("Linnea", "Stroud"), ("Bartholomew", "Okafor"), ("Giselle", "Marchetti"), ("Quentin", "Faraday"),
]
CITIES = [("Bristol", "RI", "02809"), ("Portsmouth", "NH", "03801"), ("Mystic", "CT", "06355"), ("Camden", "ME", "04843"), ("Newport", "RI", "02840")]
# (cause, LOB, estimate, injury, loss date, reported date, police report, vehicle?, prior fraud flag)
FNOL_CASES = [
    ("GLAS", "AUTO", "412.00", False, "2026-09-02", "2026-09-02", False, True, False),
    ("GLAS", "AUTO", "2499.99", False, "2026-09-03", "2026-09-04", False, True, False),
    ("TOWG", "AUTO", "185.50", False, "2026-09-05", "2026-09-05", False, True, False),
    ("COLL", "AUTO", "8450.00", False, "2026-09-06", "2026-09-07", True, True, False),
    ("COLL", "AUTO", "17200.00", True, "2026-09-08", "2026-09-09", True, True, False),
    ("THFT", "AUTO", "1002.50", False, "2026-09-10", "2026-10-13", True, True, False),
    ("WIND", "HOME", "2501.50", False, "2026-09-11", "2026-09-12", False, False, False),
    ("WATR", "HOME", "6400.00", False, "2026-09-12", "2026-09-13", False, False, False),
    ("FIRE", "HOME", "61500.00", False, "2026-09-14", "2026-09-15", True, False, False),
    ("LIAB", "HOME", "25000.00", True, "2026-09-15", "2026-09-29", False, False, False),
    ("COMP", "AUTO", "3300.00", False, "2026-09-16", "2026-09-16", False, True, True),
    ("GLAS", "AUTO", "640.00", True, "2026-09-17", "2026-09-18", False, True, False),
    ("WIND", "HOME", "4100.00", False, "2026-09-18", "2026-09-19", False, False, False),
    ("COLL", "AUTO", "5200.00", False, "2026-09-20", "2026-09-21", False, True, False),
    ("THFT", "HOME", "2200.00", False, "2026-09-21", "2026-09-22", True, False, False),
    ("COLL", "AUTO", "2000.00", False, "2026-09-22", "2026-09-23", False, True, False),
]
# (status, effective, expiration, deductible, limit)
POLICY_CASES = [
    ("Active", "2026-01-15", "2027-01-14", "250.00", "50000.00"),
    ("Active", "2025-11-01", "2026-10-31", "500.00", "100000.00"),
    ("Active", "2026-08-30", "2027-08-29", "500.00", "75000.00"),
    ("Lapsed", "2025-03-01", "2026-02-28", "1000.00", "100000.00"),
    ("Active", "2026-06-01", "2027-05-31", "500.00", "40000.00"),
    ("Active", "2026-07-20", "2027-07-19", "250.00", "25000.00"),
    ("Active", "2026-09-01", "2027-08-31", "1000.00", "300000.00"),
    ("Cancelled", "2026-01-01", "2026-06-30", "500.00", "100000.00"),
]
PAYEES = [("Harbour Collision Repair", "VN"), ("Imogen Castellanos", "CL"), ("Northlight Glass", "VN"), ("Cormac Delahunty", "CL"), ("Seaboard Restoration", "VN"), ("Penrose Salvage Yard", "SV")]
GL = {"IND": "61010100", "EXP": "61020300", "SLV": "41050200"}
REGIONS = ["NORTHEAST", "COASTAL", "INLAND"]
SKILLS = ["AUTO-PD", "AUTO-BI", "PROPERTY", "LIABILITY", "LARGE-LOSS"]
ADJUSTERS = [
    ("ADJ-101", "Sunniva Haraldsen", "NORTHEAST", "AUTO-PD,AUTO-BI", 11, 25, True),
    ("ADJ-102", "Lorcan Byrne", "NORTHEAST", "AUTO-PD", 7, 20, True),
    ("ADJ-103", "Ingrid Castellanos", "NORTHEAST", "PROPERTY,LARGE-LOSS", 19, 20, True),
    ("ADJ-104", "Mateo Quiroga", "COASTAL", "PROPERTY", 14, 25, True),
    ("ADJ-105", "Rosalind Ferreira", "COASTAL", "AUTO-PD,PROPERTY", 7, 25, True),
    ("ADJ-106", "Thaddeus Okonjo", "COASTAL", "LIABILITY,AUTO-BI", 22, 22, True),
    ("ADJ-107", "Beatrix Lindholm", "INLAND", "AUTO-PD,AUTO-BI,PROPERTY", 3, 15, False),
    ("ADJ-108", "Kwame Adjei", "INLAND", "PROPERTY,LARGE-LOSS", 9, 20, True),
    ("ADJ-109", "Helene Dubois", "INLAND", "AUTO-PD", 9, 20, True),
]


def write(path: str, body: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def fnol_message(i: int, case) -> tuple[str, str, str]:
    cause, lob, estimate, injury, loss_dt, reported_dt, police, vehicle, prior_fraud = case
    claim_no = f"CLM-2026-{100400 + i:06d}"
    policy_no = f"POL-{lob}-{48100 + (i * 7) % 900:05d}"
    agency = AGENCIES[i % len(AGENCIES)]
    given, surname = CLAIMANTS[i]
    city, state, postal = CITIES[i % len(CITIES)]
    rquid = f"6f1c3a2e-0000-4b1a-9c0d-{i:012d}"
    tax = f"{100 + i:03d}-{40 + i:02d}-{7000 + i * 13:04d}"
    phone_block = f"\n        <PhoneNumber>401-555-{1000 + i * 37:04d}</PhoneNumber>" if i % 3 else ""
    email_block = f"\n        <EmailAddr>{given.lower()}.{surname.lower()}@example.net</EmailAddr>" if i % 4 else ""
    fraud_block = f"\n        <PriorFraudFlagInd>{bool_str(prior_fraud)}</PriorFraudFlagInd>" if (prior_fraud or i % 5 == 0) else ""
    police_block = f"\n        <PoliceReportInd>{bool_str(police)}</PoliceReportInd>" if (police or i % 2) else ""
    eff_block = f"\n        <EffectiveDt>{POLICY_CASES[i % len(POLICY_CASES)][1]}</EffectiveDt>" if i % 2 == 0 else ""
    descs = {
        "GLAS": "Windscreen cracked by road debris on the interstate",
        "TOWG": "Vehicle would not start in a supermarket car park, towed to dealer",
        "COLL": "Rear-ended at a stop light; other driver admitted fault at the scene",
        "THFT": "Items stolen; discovered on return from travel",
        "WIND": "Shingles and a section of fence lost in the overnight storm",
        "WATR": "Washing machine hose burst, kitchen and hallway floor damaged",
        "FIRE": "Kitchen fire spread to cabinets and ceiling before the brigade arrived",
        "LIAB": "Visitor slipped on the icy front step and was taken to hospital",
        "COMP": "Hail damage to roof and bonnet while parked at work",
    }
    vehicle_block = ""
    if vehicle:
        vin = f"1HGCM82633A{100000 + i * 911:06d}"
        vehicle_block = f"""
      <AutoLossInfo>
        <VIN>{vin}</VIN>
        <DriveableInd>{bool_str(cause != 'COLL' or i % 2 == 0)}</DriveableInd>
      </AutoLossInfo>"""
    body = f"""<ns0:ClaimsSvcRq xmlns:ns0="{FNOL_NS}">
  <RqUID>{rquid}</RqUID>
  <TransactionRequestDt>{reported_dt}T08:{15 + i:02d}:00</TransactionRequestDt>
  <ClaimsNotificationAddRq>
    <Producer>
      <ProducerId>{agency[0]}</ProducerId>
      <ProducerName>{escape(agency[1])}</ProducerName>
    </Producer>
    <Policy>
      <PolicyNumber>{policy_no}</PolicyNumber>
      <LOBCd>{lob}</LOBCd>{eff_block}
    </Policy>
    <InsuredOrPrincipal>
      <GivenName>{given}</GivenName>
      <Surname>{surname}</Surname>
      <TaxId>{tax}</TaxId>{phone_block}{email_block}{fraud_block}
    </InsuredOrPrincipal>
    <ClaimsOccurrence>
      <ClaimNumber>{claim_no}</ClaimNumber>
      <LossDt>{loss_dt}</LossDt>
      <ReportedDt>{reported_dt}</ReportedDt>
      <LossCauseCd>{cause}</LossCauseCd>
      <IncidentDesc>{descs[cause]}</IncidentDesc>
      <EstimatedLossAmt>{estimate}</EstimatedLossAmt>
      <InjuryInd>{bool_str(injury)}</InjuryInd>{police_block}
      <Addr>
        <City>{city}</City>
        <StateProvCd>{state}</StateProvCd>
        <PostalCode>{postal}</PostalCode>
      </Addr>
    </ClaimsOccurrence>{vehicle_block}
  </ClaimsNotificationAddRq>
</ns0:ClaimsSvcRq>
"""
    return claim_no, policy_no, body


def policy_response(i: int, policy_no: str, lob: str, rquid: str) -> str:
    status, eff, exp, ded, limit = POLICY_CASES[i % len(POLICY_CASES)]
    coverages = {"AUTO": [("COLL", limit), ("COMP", limit), ("GLAS", "2500.00")], "HOME": [("DWELL", limit), ("LIAB", "300000.00")]}[lob]
    cov = "".join(f"\n  <Coverage>\n    <CoverageCd>{c}</CoverageCd>\n    <LimitAmt>{l}</LimitAmt>\n  </Coverage>" for c, l in coverages)
    return f"""<ns0:PolicyInqRs xmlns:ns0="{POLICY_NS}">
  <RqUID>{rquid}</RqUID>
  <PolicyNumber>{policy_no}</PolicyNumber>
  <PolicyStatusCd>{status}</PolicyStatusCd>
  <LOBCd>{lob}</LOBCd>
  <EffectiveDt>{eff}</EffectiveDt>
  <ExpirationDt>{exp}</ExpirationDt>
  <DeductibleAmt>{ded}</DeductibleAmt>
  <CoverageLimitAmt>{limit}</CoverageLimitAmt>
  <InsuredPartyId>PTY-{70000 + i * 31:06d}</InsuredPartyId>{cov}
</ns0:PolicyInqRs>
"""


def aggregate(part0: str, part1: str) -> str:
    def strip(doc: str) -> str:
        return "\n".join("    " + line for line in doc.rstrip("\n").splitlines())
    return f"""<ns0:Root xmlns:ns0="{AGG_NS}">
  <InputMessagePart_0>
{strip(part0)}
  </InputMessagePart_0>
  <InputMessagePart_1>
{strip(part1)}
  </InputMessagePart_1>
</ns0:Root>
"""


def payment_message(i: int) -> str:
    rng = random.Random(1000 + i)
    claim_no = f"CLM-2026-{100400 + (i * 3) % 16:06d}"
    policy_no = f"POL-AUTO-{48100 + (i * 11) % 900:05d}"
    vendor = ["PAYV01", "PAYV02"][i % 2]
    payee, ptype = PAYEES[i % len(PAYEES)]
    value_date = date(2026, 10, 1) + timedelta(days=i)
    lines = [("IND", f"{rng.randrange(20000, 1500000) / 100:.2f}", "Indemnity per adjuster estimate")]
    if i % 2 == 0:
        lines.append(("EXP", f"{rng.randrange(2500, 60000) / 100:.2f}", "Independent appraisal fee"))
    if i % 3 == 0:
        lines.append(("SLV", f"-{rng.randrange(5000, 120000) / 100:.2f}", "Salvage recovery credit"))
    if i == 7:
        lines = [("IND", "0.015", "Rounding edge: sub-cent indemnity adjustment"), ("IND", "1234.565", "Rounding edge: half cent"), ("EXP", "0.50", "Fee")]
    if i == 11:
        lines = [("IND", "999999.99", "Large loss settlement"), ("EXP", "12000.00", "Litigation expense"), ("SLV", "-25000.00", "Salvage recovery credit")]
    line_xml = "".join(
        f"""
  <Line>
    <LineNo>{n}</LineNo>
    <LineType>{t}</LineType>
    <Amount>{a}</Amount>
    <GLAccount>{GL[t]}</GLAccount>
    <Memo>{m}</Memo>
  </Line>"""
        for n, (t, a, m) in enumerate(lines, start=1)
    )
    bank = f"\n    <BankAccountMasked>****{1000 + i * 73:04d}</BankAccountMasked>" if ptype != "SV" else ""
    return f"""<ns0:PaymentInstruction xmlns:ns0="{PAY_NS}">
  <InstructionId>PI-2026-{880100 + i:06d}</InstructionId>
  <ClaimNumber>{claim_no}</ClaimNumber>
  <PolicyNumber>{policy_no}</PolicyNumber>
  <VendorCode>{vendor}</VendorCode>
  <Payee>
    <Name>{escape(payee)}</Name>
    <PayeeType>{ptype}</PayeeType>{bank}
  </Payee>
  <ValueDate>{value_date.isoformat()}</ValueDate>
  <CurrencyCd>USD</CurrencyCd>{line_xml}
</ns0:PaymentInstruction>
"""


def assignment_request(i: int) -> tuple[str, str]:
    cases = [
        ("AUTO", "COLL", "NORTHEAST", "HIGH", "AUTO-BI", "17200.00"),
        ("AUTO", "GLAS", "COASTAL", "LOW", "AUTO-PD", "412.00"),
        ("HOME", "FIRE", "NORTHEAST", "HIGH", "LARGE-LOSS", "61500.00"),
        ("HOME", "WATR", "INLAND", "MED", "PROPERTY", "6400.00"),
        ("HOME", "LIAB", "INLAND", "HIGH", "LIABILITY", "25000.00"),
        ("AUTO", "THFT", "COASTAL", "MED", "AUTO-PD", "1002.50"),
        ("HOME", "WIND", "COASTAL", "LOW", "PROPERTY", "2501.50"),
        ("AUTO", "COLL", "INLAND", "MED", "AUTO-PD", "5200.00"),
        ("HOME", "LIAB", "COASTAL", "HIGH", "LIABILITY", "48000.00"),
        ("AUTO", "COMP", "NORTHEAST", "LOW", "AUTO-PD", "3300.00"),
    ]
    lob, cause, region, severity, skill, est = cases[i]
    claim_no = f"CLM-2026-{100400 + (i * 5) % 16:06d}"
    given, surname = CLAIMANTS[(i * 5) % 16]
    requested = date(2026, 9, 24) + timedelta(days=i)
    req = f"""<ns0:AssignmentRequest xmlns:ns0="{ASG_NS}">
  <RequestId>ASG-{520100 + i:06d}</RequestId>
  <ClaimNumber>{claim_no}</ClaimNumber>
  <LineOfBusiness>{lob}</LineOfBusiness>
  <LossCause>{cause}</LossCause>
  <Region>{region}</Region>
  <Severity>{severity}</Severity>
  <RequiredSkill>{skill}</RequiredSkill>
  <RequestedDt>{requested.isoformat()}</RequestedDt>
  <ClaimantName>{given} {surname}</ClaimantName>
  <EstimatedAmount>{est}</EstimatedAmount>
</ns0:AssignmentRequest>
"""
    roster_rows = "".join(
        f"""
  <Adjuster>
    <AdjusterId>{aid}</AdjusterId>
    <Name>{name}</Name>
    <Email>{name.split()[0].lower()}.{name.split()[1].lower()}@thistlecombe.example</Email>
    <Region>{reg}</Region>
    <Skills>{skills}</Skills>
    <OpenClaims>{open_c + (i if aid == 'ADJ-102' else 0)}</OpenClaims>
    <MaxClaims>{max_c}</MaxClaims>
    <Available>{bool_str(avail)}</Available>
  </Adjuster>"""
        for aid, name, reg, skills, open_c, max_c, avail in ADJUSTERS
        if reg == region
    )
    roster = f"""<ns0:RosterResult xmlns:ns0="{ASG_NS}">{roster_rows}
</ns0:RosterResult>
"""
    return req, roster


def main() -> None:
    for i, case in enumerate(FNOL_CASES):
        claim_no, policy_no, fnol = fnol_message(i, case)
        write(os.path.join(HERE, "inputs", "fnol", f"{claim_no}.xml"), fnol)
        rquid = f"6f1c3a2e-0000-4b1a-9c0d-{i:012d}"
        policy = policy_response(i, policy_no, case[1], rquid)
        write(os.path.join(HERE, "stubs", "policy", f"{policy_no}.xml"), policy)
    for i in range(14):
        pid = f"PI-2026-{880100 + i:06d}"
        write(os.path.join(HERE, "inputs", "payment", f"{pid}.xml"), payment_message(i))
    for i in range(10):
        req, roster = assignment_request(i)
        rid = f"ASG-{520100 + i:06d}"
        write(os.path.join(HERE, "inputs", "assignment", f"{rid}.xml"), req)
        write(os.path.join(HERE, "stubs", "roster", f"{rid}.xml"), roster)
        write(os.path.join(HERE, "inputs", "assignment-enriched", f"{rid}.xml"), aggregate(roster, req))
    print("inputs: 16 fnol, 14 payment, 10 assignment; stubs: 16 policy, 10 roster; aggregates: 10 assignment-enriched")
    print("fnol-enriched aggregates are built by build_aggregates() after the canonical goldens exist")


def build_aggregates() -> None:
    """Pair each canonical Claim golden with its policy stub into the two-part map input."""
    golden_dir = os.path.join(HERE, "golden", "fnol-canonical")
    count = 0
    for name in sorted(os.listdir(golden_dir)):
        with open(os.path.join(golden_dir, name), encoding="utf-8") as fh:
            claim = fh.read()
        policy_no = claim.split("<PolicyNumber>")[1].split("</PolicyNumber>")[0]
        with open(os.path.join(HERE, "stubs", "policy", f"{policy_no}.xml"), encoding="utf-8") as fh:
            policy = fh.read()
        write(os.path.join(HERE, "inputs", "fnol-enriched", name), aggregate(claim, policy))
        count += 1
    print(f"fnol-enriched aggregates: {count}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "aggregates":
        build_aggregates()
    else:
        main()
