"""Build the Policies and Claims stub fixtures from the carrier estate's own data.

policies.json: the `policies` and `products` rows in
  services/industry-solutions/insurance/db/oltp/02_seed.sql
claims.json:   the FNOL corpus of the BizTalk claims hub
  (golden/fnol-canonical, golden/triage-facts, golden/triage), read with
  `git show` from the fixture branch so that branch is never checked out or written.

Money stays as decimal strings exactly as the source wrote it; the desktop names
its own rounding (see ../ESTATE.md).
"""
import argparse
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
SEED = "services/industry-solutions/insurance/db/oltp/02_seed.sql"
CORPUS_BRANCH = "origin/devin/1792473658-insurance-biztalk-fixture"
GOLDEN = "industries/insurance/biztalk-claims-intake/corpus/golden"


def sql_rows(sql, table):
    pattern = r"INSERT INTO %s \(([^)]*)\) VALUES\s*\((.*?)\);" % table
    for cols, vals in re.findall(pattern, sql, re.S):
        names = [c.strip() for c in cols.split(",")]
        values = [v.strip() for v in re.findall(r"DATE '[^']*'|'[^']*'|[^,]+", vals)]
        yield dict(zip(names, (re.sub(r"^(DATE )?'|'$", "", v) for v in values)))


def policies():
    with open(os.path.join(REPO, SEED), encoding="utf-8") as fh:
        sql = fh.read()
    products = {p["product_code"]: p for p in sql_rows(sql, "products")}
    out = []
    for p in sql_rows(sql, "policies"):
        prod = products[p["product_code"]]
        out.append({
            "policy_no": p["policy_no"],
            "product_code": p["product_code"],
            "product_name": prod["product_name"],
            "line_of_business": prod["line_of_business"],
            "holder_name": p["holder_name"],
            "annual_premium": p["annual_premium"],
            "issued_date": p["issued_date"],
            "status": p["status"],
        })
    return {"policies": out, "total": len(out), "source": SEED}


def git_show(path):
    return subprocess.run(["git", "-C", REPO, "show", "%s:%s" % (CORPUS_BRANCH, path)],
                          check=True, capture_output=True, text=True, encoding="utf-8").stdout


def git_ls(path):
    out = subprocess.run(["git", "-C", REPO, "ls-tree", "--name-only", "%s:%s" % (CORPUS_BRANCH, path)],
                         check=True, capture_output=True, text=True).stdout
    return sorted(n for n in out.split() if n)


def text(root, path):
    node = root.find(path)
    return None if node is None else node.text


def claims():
    out = []
    for name in git_ls(GOLDEN + "/fnol-canonical"):
        number = name.rsplit(".", 1)[0]
        fnol = ET.fromstring(git_show("%s/fnol-canonical/%s" % (GOLDEN, name)))
        facts = ET.fromstring(git_show("%s/triage-facts/%s.xml" % (GOLDEN, number)))
        triage = json.loads(git_show("%s/triage/%s.json" % (GOLDEN, number)))
        out.append({
            "claim_number": text(fnol, "ClaimNumber"),
            "policy_number": text(fnol, "PolicyNumber"),
            "line_of_business": text(fnol, "LineOfBusiness"),
            "claimant_name": text(fnol, "Claimant/FullName"),
            "loss_date": text(fnol, "Loss/LossDate"),
            "reported_date": text(fnol, "Loss/ReportedDate"),
            "cause_code": text(fnol, "Loss/CauseCode"),
            "estimated_amount": text(fnol, "Loss/EstimatedAmount"),
            "injury": text(fnol, "Loss/Injury") == "true",
            "reserve": text(facts, "ReserveEstimate"),
            "status": triage["Outcome"],
        })
    return {"claims": out, "total": len(out), "source": CORPUS_BRANCH + ":" + GOLDEN}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=HERE)
    args = parser.parse_args()
    for name, data in (("policies.json", policies()), ("claims.json", claims())):
        with open(os.path.join(args.out, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        print(name, data["total"])


if __name__ == "__main__":
    main()
