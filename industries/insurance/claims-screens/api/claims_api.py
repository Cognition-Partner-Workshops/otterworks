#!/usr/bin/env python3
"""JSON API behind the claims screens.

  --source golden  reads the BizTalk corpus goldens (biztalk-claims-intake/corpus/golden), nothing else.
  --source camel   reads what the running claims-hub-camel wrote: its tracking drop, the claims and ledger
                   tables in PostgreSQL, the vendor's SFTP inbox and the SMTP sink (MailHog).

Values are read from those outputs and passed through as written; the API never fills a gap from the other
source. Where the source has no value the field is null and `missing` says why.

Every request needs `Authorization: Bearer <token>`. CLAIMS_SCREENS_READER_TOKEN and CLAIMS_SCREENS_ADJUSTER_TOKEN
name the tokens (at least one must be set). A reader gets claimant and claimant-payee names and accounts masked
the way the claims_api PostgreSQL views mask them (compliance.mask_name / mask_account); an adjuster sees them in clear.
"""
from __future__ import annotations

import argparse
import base64
import email
import glob
import hmac
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
INSURANCE = os.path.dirname(os.path.dirname(HERE))
FIXTURE = os.environ.get("CLAIMS_FIXTURE_DIR", os.path.join(INSURANCE, "biztalk-claims-intake"))
CORPUS = os.path.join(FIXTURE, "corpus")
ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,31}$")
TOKEN_ENV = {"reader": "CLAIMS_SCREENS_READER_TOKEN", "adjuster": "CLAIMS_SCREENS_ADJUSTER_TOKEN"}
MIN_TOKEN_LENGTH = 16


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def fields(xml_text: str) -> dict[str, str | None]:
    """Child elements of the root by local name; xsi:nil and empty elements are None."""
    root = ET.fromstring(xml_text)
    out: dict[str, str | None] = {}
    for child in root:
        nil = child.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true"
        out[local(child.tag)] = None if nil or child.text is None else child.text
    return out


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def mask_keep_last(value: str | None, visible: int = 4) -> str | None:
    """compliance.mask_keep_last: separators survive, every letter or digit but the last `visible` becomes X."""
    if not value:
        return value
    out, seen = [], 0
    for ch in reversed(value):
        if ch.isalnum():
            seen += 1
            ch = "X" if seen > visible else ch
        out.append(ch)
    return "".join(reversed(out))


def mask_name(value: str | None) -> str | None:
    """compliance.mask_name: 'Imogen Castellanos' -> 'I***** C**********'."""
    if value is None:
        return None
    return " ".join(w[0] + "*" * (len(w) - 1) for w in re.split(r"\s+", value) if w) or None


def mask_account(value: str | None) -> str | None:
    return mask_keep_last(value, 4)


def is_business_payee(payee_type: str | None) -> bool:
    # claims_api.payment: vendors (VN) and salvage yards (SV) stay readable; CL payees are claimants.
    return payee_type is not None and payee_type != "CL"


def for_role(kind: str, body: dict, role: str) -> dict:
    if role == "adjuster":
        return body
    if kind == "claims":
        return {**body, "claimant": mask_name(body.get("claimant"))}
    if kind == "payments":
        payee = body.get("payee") or {}
        if not is_business_payee(payee.get("type")):
            payee = {**payee, "name": mask_name(payee.get("name")), "account": mask_account(payee.get("account"))}
        remittance = body.get("remittance")
        if remittance:
            remittance = {**remittance, "lines": [l if is_business_payee(l.get("payeeType")) else {**l, "payee": mask_name(l.get("payee"))}
                                                  for l in remittance.get("lines", [])]}
        return {**body, "payee": payee, "remittance": remittance}
    return body


def tokens_from_env(env=os.environ) -> dict[str, str]:
    """token -> role."""
    tokens: dict[str, str] = {}
    for role, var in TOKEN_ENV.items():
        token = env.get(var, "")
        if not token:
            continue
        if len(token) < MIN_TOKEN_LENGTH:
            raise ValueError(f"{var} must be at least {MIN_TOKEN_LENGTH} characters")
        if token in tokens:
            raise ValueError(f"{TOKEN_ENV[tokens[token]]} and {var} must differ")
        tokens[token] = role
    if not tokens:
        raise ValueError(f"set {' and/or '.join(TOKEN_ENV.values())}")
    return tokens


def role_for(authorization: str | None, tokens: dict[str, str]) -> str | None:
    scheme, _, presented = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not presented:
        return None
    role = None
    for token, r in tokens.items():
        if hmac.compare_digest(presented.strip().encode(), token.encode()):
            role = r
    return role


def corpus_input(kind: str, name: str) -> str:
    return os.path.join(CORPUS, "inputs", kind, name + ".xml")


def assignment_request_for(claim: str) -> str | None:
    for path in sorted(glob.glob(os.path.join(CORPUS, "inputs", "assignment", "*.xml"))):
        if fields(read(path)).get("ClaimNumber") == claim:
            return os.path.basename(path)[:-4]
    return None


def policy_from_insert(insert: dict[str, str | None]) -> dict:
    return {
        "number": insert.get("PolicyNumber"),
        "status": insert.get("PolicyStatus"),
        "lineOfBusiness": insert.get("LineOfBusiness"),
        "effectiveDate": insert.get("PolicyEffectiveDate"),
        "inForceAtLoss": insert.get("InForceAtLoss"),
    }


def adjuster_from_notice(notice: dict[str, str | None], request_id: str) -> dict:
    return {
        "requestId": request_id,
        "id": notice.get("AdjusterId"),
        "name": notice.get("AdjusterName"),
        "email": notice.get("To"),
        "severity": notice.get("Severity"),
        "slaDays": notice.get("SlaDays"),
        "escalated": notice.get("Escalated") == "true",
    }


def remittance_records(text: str) -> dict:
    """The positional file as the vendor reads it: HDR, PAY lines, TRL; plus the trailer re-check."""
    records = [r for r in text.split("\r\n") if r]
    pays = [r for r in records if r.startswith("PAY")]
    trl = next((r for r in records if r.startswith("TRL")), "")
    lines = [{
        "seq": int(r[3:7]),
        "claimNumber": r[7:22],
        "payee": r[22:52].rstrip(),
        "payeeType": r[52:54],
        "lineType": r[54:57],
        "amountCents": int(r[57:69]),
        "direction": r[69:70],
        "valueDate": r[70:78],
        "glAccount": r[78:86],
    } for r in pays]
    debit = sum(l["amountCents"] for l in lines if l["direction"] == "D")
    credit = sum(l["amountCents"] for l in lines if l["direction"] == "C")
    # Trailer: RecordType 3, PaymentCount 6, DebitTotalCents 14, CreditTotalCents 14, HashTotal 10
    trailer = {"count": int(trl[3:9]), "debitCents": int(trl[9:23]), "creditCents": int(trl[23:37]), "hashTotal": trl[37:47]} if trl else None
    if trailer:
        trailer["netCents"] = trailer["debitCents"] - trailer["creditCents"]
    recomputed = {"count": len(lines), "debitCents": debit, "creditCents": credit, "netCents": debit - credit}
    return {
        "header": records[0] if records else None,
        "vendorCode": records[0][14:20] if records else None,
        "lines": lines,
        "trailer": trailer,
        "trailerMatchesLines": bool(trailer) and all(trailer[k] == recomputed[k] for k in recomputed),
        "recomputed": recomputed,
    }


def instruction(instruction_id: str) -> dict:
    root = ET.fromstring(read(corpus_input("payment", instruction_id)))
    f = {local(c.tag): c for c in root}
    payee = {local(c.tag): c.text for c in f["Payee"]}
    lines = [{local(c.tag): c.text for c in line} for line in root if local(line.tag) == "Line"]
    return {
        "instructionId": f["InstructionId"].text,
        "claimNumber": f["ClaimNumber"].text,
        "policyNumber": f["PolicyNumber"].text,
        "vendorCode": f["VendorCode"].text,
        "valueDate": f["ValueDate"].text,
        "currency": f["CurrencyCd"].text,
        "payee": {"name": payee.get("Name"), "type": payee.get("PayeeType"), "account": payee.get("BankAccountMasked")},
        "lines": [{"lineNo": int(l["LineNo"]), "lineType": l["LineType"], "amount": l["Amount"], "glAccount": l.get("GLAccount"), "memo": l.get("Memo")} for l in lines],
    }


def ledger_view(doc: dict[str, str | None]) -> dict:
    return {k[0].lower() + k[1:]: doc.get(k) for k in ("VendorReference", "IndemnityAmount", "ExpenseAmount", "SalvageCredit", "NetAmount", "LineCount")}


def payment_differences(ledger: dict | None, remittance: dict | None) -> list[str]:
    if not ledger or not remittance or not remittance.get("trailer") or ledger.get("netAmount") is None:
        return []
    file_net = Decimal(remittance["trailer"]["netCents"]) / 100
    ledger_net = Decimal(ledger["netAmount"])
    if file_net == ledger_net:
        return []
    return [f"Ledger net {ledger_net:.2f} vs remittance file net {file_net:.2f}: Payment_to_LedgerPost rounds the summed "
            "lines once, Payment_to_VendorRemittance rounds every line to cents. The legacy hub has no rule for the cent; "
            "claims finance has to decide which amount is paid (ESTATE.md)."]


class Golden:
    name = "golden"
    label = "BizTalk corpus goldens"

    def detail(self) -> str:
        return os.path.relpath(os.path.join(CORPUS, "golden"), INSURANCE)

    def submit_fnol(self, claim: str) -> dict:
        corpus_input("fnol", claim)
        return self.fnol_result(claim)

    def fnol_result(self, claim: str) -> dict:
        triage = json.loads(read(os.path.join(CORPUS, "golden", "triage", claim + ".json")))
        outcome = triage["Outcome"]
        return {
            "claimNumber": triage["ClaimNumber"],
            "outcome": outcome,
            "reasons": triage["Reasons"],
            # FnolIntake.odx Decide_Outcome: a decline terminates the instance before usp_InsertClaim.
            "fnolStatus": "TERMINATED" if outcome == "DECLINE_NOT_IN_FORCE" else "COMPLETED",
            "evidence": [f"corpus/golden/triage/{claim}.json"],
        }

    def claim(self, claim: str) -> dict:
        result = self.fnol_result(claim)
        insert = fields(read(os.path.join(CORPUS, "golden", "insert-claim", claim + ".xml")))
        request = assignment_request_for(claim)
        adjuster, missing = None, None
        notice_path = os.path.join(CORPUS, "golden", "assignment-notice", f"{request}.xml") if request else None
        if notice_path and os.path.exists(notice_path):
            adjuster = adjuster_from_notice(fields(read(notice_path)), request)
            result["evidence"].append(f"corpus/golden/assignment-notice/{request}.xml")
        else:
            missing = "no assignment request for this claim in corpus/inputs/assignment"
        result["evidence"].append(f"corpus/golden/insert-claim/{claim}.xml")
        return {**result, "claimant": insert.get("ClaimantName"), "lossCause": insert.get("LossCause"),
                "policy": policy_from_insert(insert), "adjuster": adjuster, "missing": {"adjuster": missing} if missing else {}}

    def payment(self, instruction_id: str) -> dict:
        pi = instruction(instruction_id)
        ledger = ledger_view(fields(read(os.path.join(CORPUS, "golden", "ledger-post", instruction_id + ".xml"))))
        ff = os.path.join(CORPUS, "golden", "vendor-remittance-ff", instruction_id + ".txt")
        with open(ff, "rb") as f:
            remittance = remittance_records(f.read().decode("ascii"))
        remittance["fileName"] = os.path.basename(ff)
        return {**pi, "ledger": ledger, "remittance": remittance,
                "fileStatus": {"state": "ASSEMBLED", "detail": "Rendered by the flat file assembler (tools/ff_render.py); the corpus records no delivery."},
                "differences": payment_differences(ledger, remittance),
                "evidence": [f"corpus/golden/ledger-post/{instruction_id}.xml", f"corpus/golden/vendor-remittance-ff/{instruction_id}.txt"]}


class Camel:
    name = "camel"
    label = "claims-hub-camel outputs"

    def __init__(self, args):
        self.inbox = os.path.abspath(args.hub_inbox)
        self.sftp = os.path.abspath(args.vendor_inbox)
        self.mailhog = args.mailhog.rstrip("/")
        self.dsn = args.dsn

    def detail(self) -> str:
        return f"tracking {self.inbox}/tracking, PostgreSQL claim + ledger, SFTP {self.sftp}, MailHog {self.mailhog}"

    def query(self, sql: str, params: tuple) -> list[tuple]:
        import psycopg
        with psycopg.connect(self.dsn) as c:
            return c.execute(sql, params).fetchall()

    def tracking_path(self, claim: str) -> str:
        return os.path.join(self.inbox, "tracking", "fnol", claim + ".xml")

    def submit_fnol(self, claim: str) -> dict:
        source = corpus_input("fnol", claim)
        os.makedirs(os.path.join(self.inbox, "fnol"), exist_ok=True)
        tracking = self.tracking_path(claim)
        if os.path.exists(tracking):
            os.remove(tracking)
        tmp = os.path.join(self.inbox, "fnol", f".{claim}.tmp")
        shutil.copyfile(source, tmp)
        os.replace(tmp, os.path.join(self.inbox, "fnol", f"{claim}-{int(time.time() * 1000)}.xml"))
        deadline = time.time() + 90
        while time.time() < deadline:
            if os.path.exists(tracking):
                return self.fnol_result(claim)
            time.sleep(0.5)
        raise TimeoutError(f"the hub wrote no FnolIntake tracking record for {claim} within 90 s")

    def instance(self, claim: str) -> ET.Element:
        return ET.fromstring(read(self.tracking_path(claim)))

    def fnol_result(self, claim: str) -> dict:
        inst = self.instance(claim)
        facts = inst.find("TriageFactsRuled")
        ruled = facts[0] if facts is not None and len(facts) else None
        reasons = [c.text for c in ruled if local(c.tag) == "Reason"] if ruled is not None else []
        return {
            "claimNumber": inst.findtext("ClaimNumber"),
            "outcome": inst.findtext("TriageOutcome") or None,
            "reasons": reasons,
            "fnolStatus": inst.findtext("FnolStatus"),
            "statusReason": inst.findtext("Reason") or None,
            "evidence": [f"tracking/fnol/{claim}.xml (direct:tracking.fnol)"],
        }

    def notice_for(self, claim: str) -> tuple[dict | None, str | None]:
        with urllib.request.urlopen(f"{self.mailhog}/api/v2/messages?limit=250", timeout=5) as r:
            items = json.load(r).get("items", [])
        for item in items:
            msg = email.message_from_string(item["Raw"]["Data"])
            for part in msg.walk():
                name = part.get_filename()
                if name and name.startswith("ASG-") and name.endswith(".xml"):
                    notice = fields(part.get_payload(decode=True).decode("utf-8"))
                    if notice.get("ClaimNumber") == claim:
                        return adjuster_from_notice(notice, name[:-4]), f"SMTP {item['ID']} attachment {name}"
        return None, None

    def claim(self, claim: str) -> dict:
        result = self.fnol_result(claim)
        inst = self.instance(claim)
        insert_el = inst.find("InsertClaim")
        insert = fields(ET.tostring(insert_el[0], encoding="unicode")) if insert_el is not None and len(insert_el) else {}
        policy = policy_from_insert(insert)
        rows = self.query("select policy_number, policy_status, line_of_business, policy_effective_date::text, in_force_at_loss::text, triage_outcome from claim where claim_number = %s", (claim,))
        missing = {}
        if rows:
            n, st, lob, eff, inforce, outcome = rows[0]
            policy = {"number": n, "status": st, "lineOfBusiness": lob, "effectiveDate": eff, "inForceAtLoss": inforce}
            result["evidence"].append("PostgreSQL claim row (usp_insert_claim)")
            result["claimTableOutcome"] = outcome
        else:
            missing["claimRow"] = "no claim row: the hub did not call usp_insert_claim for this instance"
        adjuster, where = self.notice_for(claim)
        if where:
            result["evidence"].append(where)
        else:
            missing["adjuster"] = "no assignment notice for this claim in the SMTP sink"
        return {**result, "claimant": insert.get("ClaimantName"), "lossCause": insert.get("LossCause"),
                "policy": policy, "adjuster": adjuster, "missing": missing}

    def payment(self, instruction_id: str) -> dict:
        pi = instruction(instruction_id)
        rows = self.query("select entry_type, document from ledger.claim_payment_entry where instruction_id = %s order by entry_id", (instruction_id,))
        posts = [d for t, d in rows if t == "POST"]
        reversed_ = any(t == "REVERSAL" for t, _ in rows)
        ledger = ledger_view(fields(posts[0])) if posts else None
        files = sorted(glob.glob(os.path.join(self.sftp, f"REM_*_{instruction_id}.xml.txt")))
        remittance = None
        if files:
            with open(files[-1], "rb") as f:
                remittance = remittance_records(f.read().decode("ascii"))
            remittance["fileName"] = os.path.basename(files[-1])
        if remittance and posts and not reversed_:
            status = {"state": "DELIVERED", "detail": "In the vendor's SFTP inbox; ledger post standing."}
        elif reversed_:
            status = {"state": "HELD", "detail": "Ledger post reversed by the PaymentTx compensation; operations mailed."}
        elif posts:
            status = {"state": "PENDING", "detail": "Posted to the ledger; no remittance file in the vendor inbox yet."}
        else:
            status = {"state": "NOT_RECEIVED", "detail": "No ledger entry for this instruction."}
        return {**pi, "ledger": ledger, "remittance": remittance, "fileStatus": status,
                "differences": payment_differences(ledger, remittance),
                "evidence": ["PostgreSQL ledger.claim_payment_entry"] + ([f"SFTP inbound/thistlecombe/{remittance['fileName']}"] if remittance else [])}


def make_handler(source, tokens: dict[str, str]):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code: int, body: dict):
            data = json.dumps(body, indent=2).encode()
            self.send_response(code)
            if code == 401:
                self.send_header("WWW-Authenticate", 'Bearer realm="claims-screens"')
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def route(self, method: str):
            parts = [p for p in self.path.split("?")[0].split("/") if p]
            if parts[:2] != ["api", "claims-screens"]:
                return self.send(404, {"error": "not found"})
            rest = parts[2:]
            role = role_for(self.headers.get("Authorization"), tokens)
            if role is None:
                return self.send(401, {"error": "a valid bearer token is required"})
            try:
                if method == "GET" and rest == ["source"]:
                    return self.send(200, {"source": source.name, "label": source.label, "detail": source.detail()})
                if method == "GET" and rest == ["fnol"]:
                    names = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(CORPUS, "inputs", "fnol", "*.xml")))
                    return self.send(200, {"fnols": names})
                if len(rest) == 2 and ID.match(rest[1]):
                    kind, key = rest
                    if method == "POST" and kind == "fnol":
                        return self.send(200, source.submit_fnol(key))
                    if method == "GET" and kind == "claims":
                        return self.send(200, for_role(kind, source.claim(key), role))
                    if method == "GET" and kind == "payments":
                        return self.send(200, for_role(kind, source.payment(key), role))
                return self.send(404, {"error": "not found"})
            except FileNotFoundError as e:
                return self.send(404, {"error": f"not in {source.label}: {os.path.basename(e.filename or '')}"})
            except TimeoutError as e:
                return self.send(504, {"error": str(e)})

        def do_GET(self):
            self.route("GET")

        def do_POST(self):
            self.route("POST")

        def log_message(self, fmt, *args):
            sys.stderr.write(f"[{source.name}] {fmt % args}\n")

    return Handler


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=["golden", "camel"], required=True)
    p.add_argument("--port", type=int, default=8095)
    p.add_argument("--hub-inbox", default=os.path.join(HERE, "..", "hub", "run", "inbox"))
    p.add_argument("--vendor-inbox", default=os.path.join(HERE, "..", "hub", "run", "vendor-inbox"))
    p.add_argument("--mailhog", default="http://127.0.0.1:8025")
    p.add_argument("--dsn", default=os.environ.get("CLAIMS_DSN", "postgresql://claimshub:claimshub@127.0.0.1:55432/claimshub"))
    args = p.parse_args(argv)
    try:
        tokens = tokens_from_env()
    except ValueError as e:
        p.error(str(e))
    source = Golden() if args.source == "golden" else Camel(args)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(source, tokens))
    print(f"claims-screens API: {source.label} on http://127.0.0.1:{args.port}/api/claims-screens", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
