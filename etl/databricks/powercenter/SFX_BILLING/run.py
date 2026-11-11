"""Execute the scoped billing conversion and persist Statement API evidence."""

import argparse
import csv
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
ORDER = ["STG_CUSTOMER_ACCOUNT", "CUSTOMER_ACCOUNT", "STG_INVOICE_HDR",
         "INVOICE_HDR", "INVOICE_LINE", "GL_JOURNAL_LINE", "PAYMENT"]
PARAMETERS = {"LOAD_DATE": "20261109", "CURRENCY_DEFAULT": "USD", "SALES_TAX_RATE": "0.0825"}


def statements(text):
    return [part.strip() for part in text.split(";") if part.strip()]


class Runner:
    def __init__(self, step, output, ledger):
        self.step, self.output, self.ledger = step, output, ledger
        self.output.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.host = os.environ["DATABRICKS_HOST"].rstrip("/")
        if self.host.lower().startswith("http://"):
            raise ValueError("DATABRICKS_HOST must use https")
        if "://" not in self.host:
            self.host = "https://" + self.host
        if not self.host.startswith("https://"):
            raise ValueError("DATABRICKS_HOST must use https")

    def api(self, method, path, body=None):
        request = urllib.request.Request(
            self.host + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + os.environ["DATABRICKS_TOKEN"],
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def execute(self, text, purpose):
        match = re.match(r"/\* run=dbx-d1111 act=scale step=(\S+) consumer=(\S+) \*/", text)
        if not match or match[1] != self.step or "${" in text:
            raise ValueError("Missing or unresolved statement header")
        result = self.api("POST", "/api/2.0/sql/statements", {
            "statement": text, "warehouse_id": os.environ["DATABRICKS_WAREHOUSE_ID"],
            "wait_timeout": "50s", "format": "JSON_ARRAY", "disposition": "INLINE"})
        while result["status"]["state"] in ("PENDING", "RUNNING"):
            time.sleep(2)
            result = self.api("GET", "/api/2.0/sql/statements/" + result["statement_id"])
        new = not self.ledger.exists()
        with self.ledger.open("a", newline="") as f:
            writer = csv.writer(f, delimiter="\t", lineterminator="\n")
            if new:
                writer.writerow(["step", "consumer", "purpose", "statement_id", "state"])
            writer.writerow([self.step, match[2], purpose, result["statement_id"], result["status"]["state"]])
        self.results.append({"purpose": purpose, "sql": text, "result": result})
        (self.output / "statements.json").write_text(json.dumps(self.results, indent=2))
        print(purpose, result["statement_id"], result["status"]["state"], flush=True)
        if result["status"]["state"] != "SUCCEEDED":
            raise RuntimeError(result["status"].get("error"))
        return result

    def file(self, path, **extra):
        text = Template((HERE / path).read_text()).substitute(
            **PARAMETERS, STEP=self.step, **extra)
        return [self.execute(s, str(path)) for s in statements(text)]

    def query(self, consumer, purpose, sql):
        return self.execute(f"/* run=dbx-d1111 act=scale step={self.step} consumer={consumer} */\n" + sql, purpose)

    def convert(self, ddl):
        if ddl:
            self.file("00_ddl.sql")
        for mapping in ORDER:
            self.file("m_SFX_" + mapping + ".sql")

    def parity(self, run):
        report = []
        for mapping in ORDER:
            table = mapping.lower()
            left = "cpw.dbx_d1111_after.billing__sfx_" + table
            describe = self.query("m_SFX_" + mapping, "columns " + table, "DESCRIBE TABLE " + left)
            columns = [(c, t) for c, t, *_ in describe["result"]["data_array"] if c and not c.startswith("#")]
            canonical = []
            for col, typ in columns:
                if col == "journal_line_id":
                    continue
                value = f"rtrim(`{col}`)" if typ == "string" else f"CAST(`{col}` AS STRING)"
                canonical.append(f"coalesce({value},concat(char(92),'N')) AS `{col}`")
            names = ", ".join("`" + c + "`" for c, _ in columns if c != "journal_line_id")
            suffixes = ["__pc_before" + ("_run2" if run == 2 else "")]
            if mapping == "GL_JOURNAL_LINE":
                suffixes = ["__pc_before_glfix" + ("_run2" if run == 2 else ""), "__pc_before"]
            for suffix in suffixes:
                right = "cpw.dbx_d1111_parity.billing__" + table + suffix
                variables = dict(CONSUMER="m_SFX_" + mapping, LEFT_TABLE=left, RIGHT_TABLE=right,
                                 CANONICAL=", ".join(canonical), COLUMNS=names)
                comparison = self.file("parity/compare.sql", **variables)[0]
                differences = self.file("parity/differences.sql", **variables)
                entry = {"mapping": mapping, "reference": right,
                         "hash_statement_id": comparison["statement_id"],
                         "hash_rows": comparison["result"]["data_array"],
                         "differences": [{"statement_id": r["statement_id"],
                                          "rows": r.get("result", {}).get("data_array", [])} for r in differences]}
                if mapping == "GL_JOURNAL_LINE":
                    identity = self.file("parity/identity.sql", **variables)[0]
                    entry["identity"] = {"statement_id": identity["statement_id"],
                                         "rows": identity["result"]["data_array"]}
                report.append(entry)
                (self.output / "parity.json").write_text(json.dumps(report, indent=2))
        self.query("m_SFX_CUSTOMER_ACCOUNT", "duplicate source keys",
                   "SELECT customer_id,count(*) n FROM cpw.dbx_d1111_after.billing__sfx_stg_customer_account GROUP BY customer_id HAVING count(*)>1")
        self.query("m_SFX_INVOICE_HDR", "reject count",
                   "SELECT count(*) FROM cpw.dbx_d1111_after.billing__sfx_invoice_hdr__reject")
        for entry in report:
            if entry["mapping"] == "GL_JOURNAL_LINE" and entry["reference"].endswith("__pc_before"):
                continue
            left, right = entry["hash_rows"]
            if left[1:] != right[1:] or any(d["rows"] for d in entry["differences"]):
                raise ValueError("Business parity failed: " + entry["mapping"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["convert", "parity"])
    parser.add_argument("--step", required=True, choices=["convert-run1", "convert-run2", "parity", "idempotence"])
    parser.add_argument("--run", type=int, choices=[1, 2], default=1)
    parser.add_argument("--ddl", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=Path("/home/ubuntu/dbx/statements.tsv"))
    args = parser.parse_args()
    runner = Runner(args.step, args.output, args.ledger)
    if args.mode == "convert":
        runner.convert(args.ddl)
    else:
        runner.parity(args.run)


if __name__ == "__main__":
    main()
