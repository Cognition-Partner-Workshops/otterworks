"""Stand up the legacy engine locally and load the frozen window into both engines."""
import csv
import subprocess
import time

from .engines import SqlServer, Snowflake, legacy_password, stmt

CONTAINER = "wp-legacy"
IMAGE = "mcr.microsoft.com/mssql/server:2022-latest"


def legacy_up(password=None):
    password = password or legacy_password()
    running = subprocess.run(["docker", "ps", "-q", "-f", f"name={CONTAINER}"],
                             capture_output=True, text=True).stdout.strip()
    if not running:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
        subprocess.run(["docker", "run", "-d", "--name", CONTAINER, "-e", "ACCEPT_EULA=Y",
                        "-e", f"MSSQL_SA_PASSWORD={password}", "-e", "TZ=UTC",
                        "-p", "1433:1433", IMAGE], check=True)
    for _ in range(60):
        try:
            SqlServer.master()
            return
        except Exception:
            time.sleep(2)
    raise SystemExit("SQL Server did not come up within two minutes")


def _rows(path, nullable, cols):
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        header = [h.lower() for h in next(reader)]
        out = []
        for r in reader:
            out.append(tuple(None if (v == "" and nullable.get(c, True)) else v
                             for c, v in zip(header, r)))
    return header, out


def load(engine, manifest, reset=True):
    m = manifest.data
    if isinstance(engine, SqlServer):
        db = engine.database
        master = SqlServer.master()
        if reset:
            master.execute(stmt("IF DB_ID('{d}') IS NOT NULL BEGIN ALTER DATABASE {d} SET SINGLE_USER "
                                "WITH ROLLBACK IMMEDIATE; DROP DATABASE {d}; END", d=db))
        master.execute(stmt("IF DB_ID('{d}') IS NULL CREATE DATABASE {d}", d=db))
        engine = SqlServer(db)
        for f in m["legacy"]["ddl"]:
            engine.run_script(manifest.file(f).read_text())
    else:
        for f in m["snowflake"]["ddl"]:
            engine.run_script(manifest.file(f).read_text())
    counts = {}
    for table, rel in m["load"].items():
        table = engine.resolve(table)
        nullable = engine.nullability(table.replace('"', ''))
        cols, rows = _rows(manifest.file(rel), nullable, None)
        engine.execute(stmt("DELETE FROM {t}", t=table))
        engine.insert_rows(table, cols, rows)
        counts[table] = len(rows)
    if isinstance(engine, SqlServer):
        for f in m["legacy"]["code"]:
            engine.run_script(manifest.file(f).read_text())
    else:
        for f in m["snowflake"].get("code", []):
            try:
                engine.run_script(manifest.file(f).read_text())
            except Exception as exc:
                print(f"first-pass object did not compile: {f}: {str(exc).splitlines()[0]}")
    return counts
