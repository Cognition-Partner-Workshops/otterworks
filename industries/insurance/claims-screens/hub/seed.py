#!/usr/bin/env python3
"""SQL that seeds the replay database the way the hub's tests do: the WCF-SQL stand-in schema, the policy versions
from corpus/stubs/policy (LegacySystems.java, including its cancelled POL-HOME-48163 version from 2026-09-20) and the
adjuster roster from corpus/stubs/roster dated with each request's RequestedDt (RosterStubSeed.java). Prints SQL."""
import glob
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
INS = os.path.dirname(os.path.dirname(HERE))
HUB = os.path.join(INS, "claims-hub-camel", "src", "test", "resources")
CORPUS = os.path.join(INS, "biztalk-claims-intake", "corpus")
AS_OF_POLICY, AS_OF_CANCELLED_FROM = "POL-HOME-48163", "2026-09-20"


def q(v):
    return "'" + str(v).replace("'", "''") + "'"


def text(el, name):
    return next(e for e in el.iter() if e.tag.rsplit("}", 1)[-1] == name).text.strip()


def all_of(el, name):
    return [e for e in el.iter() if e.tag.rsplit("}", 1)[-1] == name]


out = [open(os.path.join(HUB, "db", "wcf-sql-stand-in.sql")).read(), open(os.path.join(HUB, "roster", "schema.sql")).read()]
for path in sorted(glob.glob(os.path.join(CORPUS, "stubs", "policy", "*.xml"))):
    rs = ET.parse(path).getroot()
    number = text(rs, "PolicyNumber")
    versions = [("-infinity", AS_OF_CANCELLED_FROM, text(rs, "PolicyStatusCd")), (AS_OF_CANCELLED_FROM, "infinity", "Cancelled")] \
        if number == AS_OF_POLICY else [("-infinity", "infinity", text(rs, "PolicyStatusCd"))]
    for frm, to, status in versions:
        out.append("insert into policy_version (policy_number, valid_from, valid_to, status_cd, lob_cd, effective_dt, expiration_dt, deductible_amt, coverage_limit_amt, insured_party_id) values "
                   f"({q(number)}, {q(frm)}::date, {q(to)}::date, {q(status)}, {q(text(rs, 'LOBCd'))}, {q(text(rs, 'EffectiveDt'))}::date, {q(text(rs, 'ExpirationDt'))}::date, "
                   f"{text(rs, 'DeductibleAmt')}, {text(rs, 'CoverageLimitAmt')}, {q(text(rs, 'InsuredPartyId'))});")
        for i, cov in enumerate(all_of(rs, "Coverage"), 1):
            out.append(f"insert into policy_coverage (policy_number, valid_from, seq, coverage_cd, limit_amt) values ({q(number)}, {q(frm)}::date, {i}, {q(text(cov, 'CoverageCd'))}, {text(cov, 'LimitAmt')});")
for stub in sorted(glob.glob(os.path.join(CORPUS, "stubs", "roster", "*.xml"))):
    as_of = text(ET.parse(os.path.join(CORPUS, "inputs", "assignment", os.path.basename(stub))).getroot(), "RequestedDt")
    for a in all_of(ET.parse(stub).getroot(), "Adjuster"):
        vals = [text(a, n) for n in ("AdjusterId", "Name", "Email", "Region", "Skills")]
        out.append("insert into adjuster_roster values (" + ", ".join([q(as_of) + "::date"] + [q(v) for v in vals])
                   + f", {int(text(a, 'OpenClaims'))}, {int(text(a, 'MaxClaims'))}, {text(a, 'Available').lower()});")
print("\n".join(out))
