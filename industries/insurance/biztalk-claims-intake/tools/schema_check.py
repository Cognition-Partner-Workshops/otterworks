"""Schema gate for the claims hub: the corpus validates and agency-controlled path identifiers are rejected.

The FILE and SFTP send ports name their targets from promoted properties
(%ClaimsHub.ClaimNumber%, %ClaimsHub.AgencyId%), and those values come from the agency's FNOL.
The schemas restrict them to CLM-nnnn-nnnnnn and AG-nnnn, so the disassembler (ValidateDocument=true)
suspends anything that could step out of the referrals, declines or fasttrack folders.

    python3 tools/schema_check.py check
"""
import copy
import glob
import os
import sys

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS = os.path.join(ROOT, "Schemas")
CORPUS = os.path.join(ROOT, "corpus")

CORPUS_SCHEMAS = {
    "inputs/fnol": "ACORD_ClaimsNotificationAddRq",
    "golden/fnol-canonical": "Canonical_Claim",
    "golden/policy-inq-rq": "ACORD_PolicyInq",
    "golden/insert-claim": "ClaimsDb_InsertClaim",
    "golden/triage-facts": "TriageFacts",
    "inputs/payment": "Canonical_PaymentInstruction",
    "golden/ledger-post": "ClaimsDb_LedgerPost",
    "golden/vendor-remittance": "PaymentVendor_Remittance_FF",
    "inputs/assignment": "AdjusterAssignment",
    "golden/roster-query": "AdjusterAssignment",
    "golden/assignment-notice": "AdjusterAssignment",
}

HOSTILE = [
    "..\\..\\..\\disbursements\\x",
    "../../../disbursements/x",
    "CLM-2026-100400\\..\\..\\x",
    "CLM-2026-100400/../x",
    "AG-0417\\..\\AG-0922",
    "..",
    "C:\\Windows\\x",
    "\\\\evil\\share\\x",
    "CLM-2026-100400 ",
    "CLM-2026-1004000",
    "CLM-\u0662\u0660\u0662\u0666-100400",
    "AG-04171",
    "",
]

ENVELOPE_NS = "http://schemas.thistlecombe.example/acord/claims/fnol/envelope"


def schema(name: str) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(os.path.join(SCHEMAS, name + ".xsd")))


def first(path: str) -> str:
    return sorted(glob.glob(os.path.join(CORPUS, path, "*.xml")))[0]


def with_value(doc: etree._ElementTree, xpath: str, value: str) -> etree._ElementTree:
    doc = copy.deepcopy(doc)
    nodes = doc.xpath(xpath)
    assert nodes, xpath
    for node in nodes:
        node.text = value
    return doc


def fnol_batch(fnol: etree._ElementTree, agency_id: str) -> etree._ElementTree:
    batch = etree.Element(f"{{{ENVELOPE_NS}}}FnolBatch", nsmap={"ns0": ENVELOPE_NS})
    header = etree.SubElement(batch, "BatchHeader")
    for tag, text in (("BatchId", "B-1"), ("AgencyId", agency_id), ("CreatedDt", "2026-10-19T22:00:00"), ("MessageCount", "1")):
        etree.SubElement(header, tag).text = text
    etree.SubElement(batch, "Body").append(copy.deepcopy(fnol.getroot()))
    return etree.ElementTree(batch)


def check() -> int:
    failures = []
    total = 0
    for rel, name in CORPUS_SCHEMAS.items():
        xsd = schema(name)
        files = sorted(glob.glob(os.path.join(CORPUS, rel, "*.xml")))
        if not files:
            failures.append(f"{rel}: no files")
        for f in files:
            total += 1
            if not xsd.validate(etree.parse(f)):
                failures.append(f"{rel}/{os.path.basename(f)}: {xsd.error_log.last_error}")
    print(f"corpus: {total} documents validated against their schemas")

    fnol = etree.parse(first("inputs/fnol"))
    cases = [
        ("ACORD_ClaimsNotificationAddRq", fnol, "//ClaimsOccurrence/ClaimNumber"),
        ("ACORD_ClaimsNotificationAddRq", fnol, "//Producer/ProducerId"),
        ("Canonical_Claim", etree.parse(first("golden/fnol-canonical")), "/*/ClaimNumber"),
        ("Canonical_Claim", etree.parse(first("golden/fnol-canonical")), "/*/Agency/Id"),
        ("ClaimsDb_InsertClaim", etree.parse(first("golden/insert-claim")), "/*/ClaimNumber"),
        ("ClaimsDb_InsertClaim", etree.parse(first("golden/insert-claim")), "/*/AgencyId"),
        ("TriageFacts", etree.parse(first("golden/triage-facts")), "/*/ClaimNumber"),
        ("Canonical_PaymentInstruction", etree.parse(first("inputs/payment")), "/*/ClaimNumber"),
        ("ClaimsDb_LedgerPost", etree.parse(first("golden/ledger-post")), "/*/ClaimNumber"),
        ("AdjusterAssignment", etree.parse(first("inputs/assignment")), "/*/ClaimNumber"),
    ]
    rejected = 0
    for name, doc, xpath in cases:
        xsd = schema(name)
        for value in HOSTILE:
            if xsd.validate(with_value(doc, xpath, value)):
                failures.append(f"{name} {xpath} accepted {value!r}")
            else:
                rejected += 1

    envelope = schema("FnolBatchEnvelope")
    if not envelope.validate(fnol_batch(fnol, "AG-0417")):
        failures.append(f"FnolBatchEnvelope rejected a well-formed batch: {envelope.error_log.last_error}")
    for value in HOSTILE:
        if envelope.validate(fnol_batch(fnol, value)):
            failures.append(f"FnolBatchEnvelope BatchHeader/AgencyId accepted {value!r}")
        else:
            rejected += 1
        if envelope.validate(fnol_batch(with_value(fnol, "//ClaimsOccurrence/ClaimNumber", value), "AG-0417")):
            failures.append(f"FnolBatchEnvelope Body ClaimNumber accepted {value!r}")
        else:
            rejected += 1
    print(f"path identifiers: {rejected} hostile ClaimNumber/AgencyId values rejected")

    for line in failures:
        print("FAIL", line)
    return 1 if failures else 0


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        sys.exit(__doc__)
    sys.exit(check())
