#!/usr/bin/env python3
"""One row per corpus unit: what the running claims-hub-camel wrote against the BizTalk golden for it.

FNOL (16): outcome + reasons (corpus/golden/triage) and the TriageFacts the hub ruled (corpus/golden/triage-facts,
Outcome/Reason stripped). Assignment (10): the SMTP attachment against corpus/golden/assignment-notice, byte for byte.
Payment (14): the ledger post document against corpus/golden/ledger-post and the SFTP file against
corpus/golden/vendor-remittance-ff, byte for byte, plus ledger net vs file net. Nothing is normalised.
Writes markdown to stdout; exit 1 if a row differs from its golden."""
import email
import glob
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
import claims_api as api  # noqa: E402

RUN = os.path.join(HERE, "run")
G = os.path.join(api.CORPUS, "golden")
camel = api.Camel(type("A", (), {"hub_inbox": os.path.join(RUN, "inbox"), "vendor_inbox": os.path.join(RUN, "vendor-inbox"),
                                  "mailhog": "http://127.0.0.1:8025", "dsn": "postgresql://claimshub:claimshub@127.0.0.1:55432/claimshub"}))
rows, red = [], 0


def row(unit, kind, ok, note):
    global red
    red += 0 if ok else 1
    rows.append(f"| {unit} | {kind} | {'green' if ok else 'red'} | {note} |")


def strip_ruling(xml):
    return re.sub(r"<(Outcome|Reason)>[^<]*</\1>", "", re.sub(r"^<\?xml[^>]*\?>", "", xml))


for path in sorted(glob.glob(os.path.join(api.CORPUS, "inputs", "fnol", "*.xml"))):
    claim = os.path.basename(path)[:-4]
    golden = json.load(open(os.path.join(G, "triage", claim + ".json")))
    if not os.path.exists(camel.tracking_path(claim)):
        row(claim, "FNOL", False, "no tracking record: not processed")
        continue
    got = camel.fnol_result(claim)
    inst = camel.instance(claim)
    facts = ET.tostring(inst.find("TriageFactsRuled")[0], encoding="unicode") if len(inst.find("TriageFactsRuled")) else ""
    golden_facts = open(os.path.join(G, "triage-facts", claim + ".xml"), encoding="utf-8").read()
    same_facts = ET.canonicalize(strip_ruling(facts)) == ET.canonicalize(strip_ruling(golden_facts))
    ok = got["outcome"] == golden["Outcome"] and got["reasons"] == golden["Reasons"] and same_facts
    row(claim, "FNOL", ok, f"{got['fnolStatus']} {got['outcome']} / golden {golden['Outcome']}" + ("" if same_facts else "; TriageFacts differ"))

with urllib.request.urlopen("http://127.0.0.1:8025/api/v2/messages?limit=250", timeout=5) as r:
    mails = json.load(r)["items"]
notices = {}
for item in mails:
    for part in email.message_from_string(item["Raw"]["Data"]).walk():
        name = part.get_filename()
        if name and name.startswith("ASG-"):
            notices[name[:-4]] = part.get_payload(decode=True)
for path in sorted(glob.glob(os.path.join(G, "assignment-notice", "*.xml"))):
    req = os.path.basename(path)[:-4]
    want = open(path, "rb").read()
    got = notices.get(req)
    row(req, "Assignment", got == want, "notice attachment identical" if got == want else ("no notice" if got is None else "notice bytes differ"))

for path in sorted(glob.glob(os.path.join(api.CORPUS, "inputs", "payment", "*.xml"))):
    pi = os.path.basename(path)[:-4]
    docs = camel.query("select document from ledger.claim_payment_entry where instruction_id = %s and entry_type = 'POST'", (pi,))
    ledger_ok = bool(docs) and ET.canonicalize(docs[0][0]) == ET.canonicalize(open(os.path.join(G, "ledger-post", pi + ".xml"), encoding="utf-8").read())
    files = sorted(glob.glob(os.path.join(RUN, "vendor-inbox", f"REM_*_{pi}.xml.txt")))
    file_ok = bool(files) and open(files[-1], "rb").read() == open(os.path.join(G, "vendor-remittance-ff", pi + ".txt"), "rb").read()
    p = camel.payment(pi)
    note = f"ledger post {'identical' if ledger_ok else 'differs'}, remittance file {'identical' if file_ok else 'differs'}, {p['fileStatus']['state']}"
    # the divergence is in the golden too; the row is red because the two documents disagree on what is paid
    ok = ledger_ok and file_ok and not p["differences"]
    if p["differences"]:
        note += "; " + p["differences"][0]
    row(pi, "Payment", ok, note)

print("| Unit | Kind | Parity | Camel output vs BizTalk golden |\n|---|---|---|---|\n" + "\n".join(rows))
print(f"\n{len(rows) - red} green, {red} red of {len(rows)}")
sys.exit(1 if red else 0)
