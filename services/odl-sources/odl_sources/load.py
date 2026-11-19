import argparse
import csv
import os
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime
from decimal import Decimal
from itertools import islice
from pathlib import Path

from .generate import Settings, accounts, cases, contacts, customers, history, products, subscriptions

ROOT = Path(__file__).resolve().parents[1]


def batches(rows, size=2000):
    iterator = iter(rows)
    while batch := list(islice(iterator, size)):
        yield batch


def postgres(settings):
    import psycopg
    with psycopg.connect(host=os.environ["DB_HOST"], port=os.getenv("DB_PORT", "5432"),
                         dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
                         password=os.environ["DB_PASSWORD"], connect_timeout=15) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1795112287)")
        conn.execute("CREATE SCHEMA IF NOT EXISTS crm")
        conn.execute("CREATE TABLE IF NOT EXISTS crm.seed_version (version text PRIMARY KEY)")
        if conn.execute("SELECT version FROM crm.seed_version").fetchone() == (settings.version,):
            return
        conn.execute((ROOT / "postgres/ddl.sql").read_text())
        for table, source in (("contacts", contacts(settings)), ("service_cases", cases(settings)),
                              ("subscription_snapshots", subscriptions(settings))):
            with conn.cursor().copy(f"COPY crm.{table} FROM STDIN") as copy:
                for row in source:
                    copy.write_row(tuple(row.values()))
        conn.execute("DELETE FROM crm.seed_version")
        conn.execute("INSERT INTO crm.seed_version VALUES (%s)", (settings.version,))
        print("CRM rows loaded:", settings.pg_contacts, settings.pg_contacts * 2, flush=True)


def oracle(settings):
    import oracledb
    with oracledb.connect(user=os.environ["ORACLE_USER"], password=os.environ["ORACLE_PASSWORD"],
                          dsn=os.getenv("ORACLE_DSN", "oracle:1521/FREEPDB1")) as conn:
        cur = conn.cursor()
        cur.execute("ALTER SESSION SET TIME_ZONE = 'America/New_York'")
        cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name='SEED_VERSION'")
        if cur.fetchone()[0]:
            cur.execute("SELECT version FROM seed_version")
            if cur.fetchone() == (settings.version,):
                return
        for statement in (ROOT / "oracle/ddl.sql").read_text().split(";"):
            if statement.strip():
                try:
                    cur.execute(statement)
                except oracledb.DatabaseError as error:
                    if error.args[0].code != 955:
                        raise
        for table in ("ACCOUNTS", "PRODUCTS", "SEED_VERSION"):
            cur.execute(f"DELETE FROM {table}")
        cur.executemany("INSERT INTO products VALUES (:1,:2)", [tuple(r.values()) for r in products()])
        for batch in batches(accounts(settings)):
            cur.executemany("INSERT INTO accounts VALUES (:1,:2,:3,:4,:5,:6)", [
                (r["account_id"], r["holder_name"], r["address"], r["product_id"], Decimal(r["balance"]),
                 datetime.strptime(r["opened_at"], "%Y-%m-%d %H:%M:%S")) for r in batch])
        cur.execute("INSERT INTO seed_version VALUES (:1)", [settings.version])
        conn.commit()
        print("Oracle rows loaded:", settings.oracle_accounts, flush=True)


def db2_exec(command, check=True):
    command += "; status=$?; db2 -o- connect reset >/dev/null 2>&1; db2 -o- terminate >/dev/null 2>&1; exit $status"
    return subprocess.run(["kubectl", "exec", "db2-archive-0", "--", "su", "-", "db2inst1", "-c", command],
                          check=check, capture_output=True, text=True)


def db2(settings):
    if db2_exec("db2 connect to ODL >/dev/null", check=False).returncode:
        raise RuntimeError("Db2 is starting")
    version = db2_exec("db2 connect to ODL >/dev/null && db2 -x 'SELECT VERSION FROM ODL.SEED_VERSION'", check=False)
    if version.returncode == 0 and version.stdout.strip() == settings.version:
        return
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "tables.sql").write_text((ROOT / "db2/ddl.sql").read_text())
        with (root / "customers.sql").open("w") as output:
            for batch in batches(customers(settings), 500):
                values = [f"('{r['cust_no']}',X'{r['full_name']}','{r['address']}','{r['opened_on']}',{r['opened_ymd']})" for r in batch]
                output.write("INSERT INTO ODL.CUSTMAST VALUES " + ",".join(values) + ";\n")
        with (root / "history.del").open("w", newline="") as output:
            writer = csv.writer(output, lineterminator="\n")
            for row in history(settings):
                writer.writerow(row.values())
        (root / "finish.sql").write_text(f"INSERT INTO ODL.SEED_VERSION VALUES ('{settings.version}');\n")
        with tempfile.TemporaryFile() as archive:
            with tarfile.open(fileobj=archive, mode="w") as bundle:
                for path in sorted(root.iterdir()):
                    bundle.add(path, arcname=path.name)
            archive.seek(0)
            subprocess.run(["kubectl", "exec", "-i", "db2-archive-0", "--", "tar", "xf", "-", "-C", "/seed"],
                           stdin=archive, check=True, stdout=subprocess.DEVNULL)
        commands = ["db2 connect to ODL", "db2 'CREATE SCHEMA ODL' >/dev/null 2>&1 || true"]
        for table in ("ACCTHIST", "CUSTMAST", "SEED_VERSION"):
            commands.append(f"db2 'DROP TABLE ODL.{table}' >/dev/null 2>&1 || true")
        commands += ["db2 -stf /seed/tables.sql", "db2 -stf /seed/customers.sql",
                     "db2 'LOAD FROM /seed/history.del OF DEL INSERT INTO ODL.ACCTHIST NONRECOVERABLE'",
                     "db2 -x 'SELECT COUNT(*) FROM ODL.ACCTHIST' > /seed/history.count",
                     f"test \"$(tr -d ' ' < /seed/history.count)\" = {settings.db2_history}",
                     "db2 -stf /seed/finish.sql"]
        result = db2_exec("set -e; " + "; ".join(commands), check=False)
        if result.returncode:
            print(result.stdout[-3000:], flush=True)
            raise RuntimeError("Db2 load did not complete")
        print("Db2 rows loaded:", settings.db2_customers, settings.db2_history, flush=True)


def load_with_retry(source, settings):
    deadline = time.monotonic() + int(os.getenv("ODL_WAIT_SECONDS", "480"))
    while True:
        try:
            globals()[source](settings)
            return
        except Exception as error:
            if time.monotonic() >= deadline:
                raise
            print("Waiting for", source, type(error).__name__, flush=True)
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=("db2", "oracle", "postgres"))
    args = parser.parse_args()
    load_with_retry(args.source, Settings.environment())


if __name__ == "__main__":
    main()
