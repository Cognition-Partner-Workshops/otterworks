"""Rebuild the branch-tip inventory from source and the local demo evidence."""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg
import yaml
from defusedxml import ElementTree
from psycopg.rows import dict_row


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "tools"))
from assess import clean, ddl_objects  # noqa: E402

TD = ROOT / "warehouse/teradata"
PC = ROOT / "etl/informatica"
SPARK = ROOT / "etl/spark"
START, END = "2026-08-12", "2026-11-09"
KINDS = {"T": "table", "V": "view", "M": "macro", "P": "procedure"}
QUALIFIED = r"(?:SFX_[A-Z]+|DBC)\.[A-Z_]\w*"
AREAS = {"DBC": ("platform", 1), "SFX_USERS": ("users", 2),
         "SFX_DOCUMENTS": ("documents", 3), "SFX_BILLING": ("billing", 4),
         "SFX_AUDIT": ("audit", 5)}


def records(path, delimiter="|"):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def database(port, spark_port):
    with psycopg.connect(host="127.0.0.1", port=port, dbname="teradata",
                         user="postgres", row_factory=dict_row) as conn:
        activity = conn.execute((HERE / "query_history.sql").read_text()).fetchall()
        catalog = conn.execute("""
            SELECT upper(DatabaseName || '.' || TableName) AS name, TableKind AS kind FROM DBC.TablesV
        """).fetchall()
        relations = conn.execute("""
            SELECT upper(table_schema || '.' || table_name) AS name, table_type AS kind
            FROM information_schema.tables
            WHERE table_schema IN ('sfx_users', 'sfx_billing', 'sfx_documents', 'sfx_audit', 'dbc')
        """).fetchall()
        routines = conn.execute("SELECT upper(name) AS name, lower(kind) AS kind FROM sfx_td.routines").fetchall()
        totals = conn.execute("""
            SELECT count(*) AS requests, count(*) FILTER (WHERE ErrorCode <> 0) AS failed_requests
            FROM DBC.QryLogV WHERE StartTime >= %s AND StartTime < %s
        """, (START, "2026-11-10")).fetchone()
    # This is the local Spark runtime's separate JDBC database, with its fixture credentials.
    with psycopg.connect(host="127.0.0.1", port=spark_port, dbname="sfx_teradata",
                         user="etl_batch", password=os.environ["SFG_SPARK_DB_PASSWORD"],
                         row_factory=dict_row) as conn:
        spark_tables = conn.execute("""
            SELECT upper(table_schema || '.' || table_name) AS name FROM information_schema.tables
            WHERE table_schema LIKE 'sfx_%' AND starts_with(lower(table_name), 'spark_')
        """).fetchall()
    installed = {row["name"]: {"BASE TABLE": "table", "VIEW": "view"}[row["kind"]]
                 for row in relations}
    installed.update({row["name"]: row["kind"] for row in routines})
    return activity, {row["name"]: KINDS[row["kind"]] for row in catalog}, installed, totals, spark_tables


class Inventory:
    def __init__(self):
        self.nodes = {}
        self.edges = set()

    def add(self, name, kind, source=None, **fields):
        if name in self.nodes and self.nodes[name]["kind"] != kind:
            raise ValueError(f"Conflicting node kind for {name}")
        self.nodes[name] = dict(name=name, kind=kind, **fields)
        if source:
            self.nodes[name]["source"] = str(source.relative_to(ROOT))

    def edge(self, source, target, kind):
        self.edges.add((source, target, kind))

    def feed(self, area, name):
        key = f"landing:{area}/{name}"
        if key not in self.nodes:
            self.add(key, "landing feed", subject_area=area)
        return key

    def sql(self, name, statement):
        statement = clean(statement)
        for kind, pattern in (
            ("reads", rf"(?<!DELETE )\b(?:FROM|JOIN|USING)\s+({QUALIFIED})\b"),
            ("calls", rf"\b(?:CALL|EXEC(?:UTE)?)\s+({QUALIFIED})\b"),
            ("writes", rf"\b(?:INSERT\s+INTO|MERGE\s+INTO|UPDATE|DELETE\s+FROM)\s+({QUALIFIED})\b"),
        ):
            for relation in re.findall(pattern, statement, re.I):
                if kind == "writes":
                    self.edge(name, relation.upper(), kind)
                else:
                    self.edge(relation.upper(), name, kind)

    def warehouse(self):
        definitions = {}
        for path in sorted((TD / "ddl").glob("*/*.sql")) + [TD / "dbql/schema.sql"]:
            for kind, name, statement in ddl_objects(path.read_text()):
                definitions[name] = (kind, path, statement)
        for folder in ("macros", "procedures"):
            for path in sorted((TD / folder).glob("*.sql")):
                statement = path.read_text()
                match = re.search(rf"\b(?:REPLACE|CREATE)\s+(MACRO|PROCEDURE)\s+({QUALIFIED})", statement, re.I)
                definitions[match[2].upper()] = (match[1].lower(), path, statement)
        for name, (kind, path, statement) in definitions.items():
            area, wave = AREAS[name.split(".")[0]]
            self.add(name, kind, path, subject_area=area, wave=1 if ".STG_" in name else wave)
            self.sql(name, statement)

        for path in sorted((TD / "scripts").glob("*/*.bteq")):
            area = path.parent.name
            key = f"bteq:{area}/{path.stem}"
            self.add(key, "BTEQ", path, subject_area=area)
            self.sql(key, path.read_text())
        reconcile = "bteq:jobs/reconcile"
        self.add(reconcile, "BTEQ", TD / "jobs/reconcile", subject_area="audit")
        for name in ("SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY", "SFX_DOCUMENTS.STORAGE_USAGE_DAILY"):
            self.edge(name, reconcile, "reads")
        self.edge(reconcile, "SFX_AUDIT.AUDIT_RECON", "writes")

        for folder, pattern in (("fastload", "*.fl"), ("tpt", "*.tpt")):
            for path in sorted((TD / "load" / folder).glob(pattern)):
                statement = path.read_text()
                area, feed = re.search(r"\$\{LANDING_DIR\}/(\w+)/(\w+)", statement).groups()
                key = f"{folder}:{path.stem}"
                self.add(key, folder, path, subject_area=area)
                self.edge(self.feed(area, feed), key, "reads")
                self.sql(key, statement)
        return {name: kind for name, (kind, _, _) in definitions.items()}

    def powercenter(self, sessions_path):
        history = defaultdict(list)
        local = defaultdict(list)
        for row in records(PC / "logs/REP_SESS_LOG.psv"):
            history[row["MAPPING_NAME"]].append(row)
        for row in records(sessions_path):
            local[row["MAPPING_NAME"]].append(row)

        tables = defaultdict(list)
        for name, node in self.nodes.items():
            if node["kind"] == "table" and name.startswith("SFX_"):
                tables[name.split(".")[-1]].append(name)

        def relation(definition):
            name = definition.attrib["NAME"].upper()
            owner = definition.get("OWNERNAME")
            candidates = tables[name]
            if owner:
                candidates = [table for table in candidates if table.startswith(owner.upper() + ".")]
            if len(candidates) != 1:
                raise ValueError(f"Ambiguous PowerCenter relation {name}: {candidates}")
            return candidates[0]

        for path in sorted((PC / "repository").glob("*/mappings/*.XML")):
            folder = path.parents[1].name
            tree = ElementTree.parse(path)
            mapping = tree.find(".//MAPPING")
            key = mapping.attrib["NAME"]
            workflow_path = path.parents[1] / f"wf_{folder}_DAILY.XML"
            workflow = ElementTree.parse(workflow_path)
            sessions = {node.attrib["NAME"]: node for node in workflow.findall(".//SESSION")
                        if node.attrib["MAPPINGNAME"] == key}
            invocations = [
                {"workflow": f"wf_{folder}_DAILY", "session": task.attrib["TASKNAME"],
                 "enabled": task.attrib.get("ISENABLED", "YES") == "YES"}
                for task in workflow.findall(".//TASKINSTANCE") if task.get("TASKNAME") in sessions
            ]
            successes = [row["ACTUAL_START"] for row in history[key] if row["RUN_STATUS"] == "SUCCEEDED"]
            window = Counter(row["RUN_STATUS"] for row in history[key]
                             if START <= row["ACTUAL_START"][:10] <= END)
            self.add(key, "mapping", path, workflow_source=str(workflow_path.relative_to(ROOT)),
                     invocations=invocations, history_statuses=dict(sorted(window.items())),
                     last_success=max(successes, default=None),
                     local_statuses=sorted({row["RUN_STATUS"] for row in local[key]}))
            for invocation in invocations:
                name = f'{folder}/{invocation["session"]}'
                self.add(name, "session", workflow_path, enabled=invocation["enabled"])
                self.edge(key, name, "scheduled by")
            definitions = {node.attrib["NAME"]: node for tag in ("SOURCE", "TARGET")
                           for node in tree.findall(f".//{tag}")}
            destinations = set()
            for instance in mapping.findall("INSTANCE"):
                role = instance.get("TYPE")
                if role not in ("SOURCE", "TARGET"):
                    continue
                definition = definitions[instance.attrib["TRANSFORMATION_NAME"]]
                name = definition.attrib["NAME"].upper()
                if role == "TARGET":
                    table = relation(definition)
                    destinations.add(table)
                    self.edge(key, table, "writes")
                elif definition.get("DATABASETYPE") == "Flat File":
                    name = name.removeprefix("FF_")
                    self.edge(self.feed(self.feed_area(name), name), key, "reads")
                else:
                    self.edge(relation(definition), key, "reads")
            areas = {self.nodes[table]["subject_area"] for table in destinations}
            if len(areas) != 1:
                raise ValueError(f"Expected one target subject area for {key}: {areas}")
            self.nodes[key].update(subject_area=areas.pop(),
                                   wave=max(self.nodes[table]["wave"] for table in destinations))
            for attr in mapping.findall(".//TABLEATTRIBUTE"):
                if attr.get("NAME") == "Lookup table name":
                    self.edge(attr.attrib["VALUE"].upper(), key, "lookup")
                elif "sql" in attr.attrib["NAME"].lower():
                    self.sql(key, attr.attrib["VALUE"])
            for session in sessions.values():
                for attr in session.findall(".//ATTRIBUTE"):
                    if attr.get("NAME") in ("Pre SQL", "Post SQL"):
                        self.sql(key, attr.attrib["VALUE"])

    def feed_area(self, name):
        match = [node["subject_area"] for node in self.nodes.values()
                 if node["kind"] == "landing feed" and node["name"].endswith("/" + name)]
        if len(match) != 1:
            raise ValueError(f"Ambiguous landing feed {name}: {match}")
        return match[0]

    def spark(self, statuses, history, retries):
        jobs = (SPARK / "jobs.txt").read_text().split()
        registry = {path.stem for path in (SPARK / "jobs/registry").glob("*.yaml")}
        if set(jobs) != registry or set(jobs) != statuses.keys() or set(jobs) != history.keys():
            raise ValueError("Spark job list, registry, local results and bundled history must agree")
        if not retries.keys() <= statuses.keys():
            raise ValueError(f"Unknown Spark retry jobs: {sorted(retries.keys() - statuses.keys())}")
        python = {path.stem: path for path in (SPARK / "jobs/py").glob("*.py")}
        scala = {match[1]: path for path in (SPARK / "scala/src/main/scala/sfx").glob("*.scala")
                 if (match := re.search(r'BatchSupport.session\("([^"]+)"\)', path.read_text()))}
        output_tables = set()
        for job in jobs:
            path = python.get(job) or scala[job]
            statement = path.read_text()
            cron = SPARK / "cron.d" / job
            active = any(line.strip() and not line.lstrip().startswith("#") for line in cron.read_text().splitlines())
            # Runtime helpers land Spark CSVs under /opt/landing and write Parquet under /opt/lake.
            # Only jdbc_read() takes warehouse relation inputs.
            area = re.search(rf'"(billing|documents|users|audit)"\s*,\s*"{job}"|/opt/lake/(\w+)/{job}',
                             statement)
            area = area[1] or area[2]
            key = f"spark:{job}"
            self.add(key, "Spark job", path, subject_area=area, scheduled=active,
                     cron=str(cron.relative_to(ROOT)), local_status=retries.get(job, statuses[job]),
                     local_attempts=[statuses[job]] + ([retries[job]] if job in retries else []),
                     event_history=history[job])
            for match in re.findall(r'\b(?:landing|register)\(spark, ([^\n]*)\)', statement):
                args = re.match(r'"[^"]+"(?:,\s*"[^"]+")*', match)[0]
                for table in re.findall(r'"([A-Z][A-Z_]+)"', args):
                    self.edge(self.feed(self.feed_area(table), table), key, "reads")
            if job == "file_object_binary_extract":
                self.edge(self.feed("documents", "FILE_OBJECT_BLOBS"), key, "reads")
            for table in re.findall(r'jdbc_read\(spark, "([^"]+)"\)', statement):
                self.edge(table.upper(), key, "reads")
            lake = f"lake:{area}/{job}"
            self.add(lake, "Parquet output", subject_area=area)
            self.edge(key, lake, "writes")
            for feed_area, dataset in set(re.findall(r'/opt/lake/(\w+)/(\w+)', statement)):
                if dataset != job:
                    self.edge(f"lake:{feed_area}/{dataset}", key, "reads")
            for table in re.findall(r'"(sfx_\w+\.SPARK_\w+)"', statement):
                table = table.upper()
                self.add(table, "Spark JDBC output", subject_area=area)
                self.edge(key, table, "writes")
                output_tables.add(table)
        return output_tables

    def assess(self, activity, warehouse):
        registry = yaml.safe_load((ROOT / "consumers/registry.yaml").read_text())["consumers"]
        accounts = {row["teradata_service_account"]: row for row in registry}
        evidence = defaultdict(list)
        active = {name for name, node in self.nodes.items() if node["kind"] == "BTEQ"
                  or node["kind"] == "Spark job" and node["scheduled"]
                  or node["kind"] == "mapping" and (node["history_statuses"].get("SUCCEEDED")
                                                     or any(i["enabled"] for i in node["invocations"]))}
        observed = set()
        for row in activity:
            name, principal, usage = row["object"], row["principal"], row["usage"]
            evidence[name].append({k: v for k, v in row.items() if k != "object"})
            if usage in ("READ", "EXECUTE") and row["successful"]:
                account = accounts.get(principal, {})
                self.add(principal, "DBQL principal", consumer=account.get("name"), owner=account.get("team"))
                self.edge(name, principal, f"DBQL {usage}")
                observed.add(name)
        for principal, account in accounts.items():
            self.add(principal, "DBQL principal", consumer=account["name"], owner=account["team"])
            active.add(principal)
            for name in account["tables"]:
                self.edge(name, principal, "declared consumer")

        missing = {endpoint for source, target, _ in self.edges for endpoint in (source, target)} - self.nodes.keys()
        if missing:
            raise ValueError(f"Unresolved lineage nodes: {sorted(missing)}")

        # Work back from runnable jobs, declared consumers and successful DBQL reads.
        # Write edges never manufacture readership (including an active writer of an unused table).
        active |= observed
        while True:
            upstream = {src for src, dst, kind in self.edges if dst in active
                        and kind in ("reads", "lookup", "calls", "declared consumer")}
            if upstream <= active:
                break
            active |= upstream

        for name, node in self.nodes.items():
            if name not in warehouse and node["kind"] != "mapping":
                continue
            incoming = [(src, kind) for src, dst, kind in sorted(self.edges) if dst == name]
            outgoing = [(dst, kind) for src, dst, kind in sorted(self.edges) if src == name]
            upstream_types = ("reads", "lookup", "calls")
            node["reads_from"] = [dict(name=src, relationship=kind) for src, kind in incoming if kind in upstream_types]
            node["written_by"] = [src for src, kind in incoming if kind == "writes"]
            node["read_by"] = [dict(name=dst, relationship=kind) for dst, kind in outgoing if kind != "writes"]
            node["writes_to"] = [dst for dst, kind in outgoing if kind == "writes"]
            if name in warehouse:
                node["dbql"] = evidence[name]
                successes = [row for row in evidence[name]
                             if row["usage"] in ("READ", "EXECUTE") and row["successful"]]
                if successes and all(row["successful"] == row["first_day_successful"] for row in successes):
                    node["status"] = "observed on first day only"
                elif successes:
                    node["status"] = "observed in DBQL"
                else:
                    node["status"] = "active dependency" if name in active else "retire candidate"
            else:
                node["status"] = ("observed in PowerCenter" if node["history_statuses"].get("SUCCEEDED")
                                  else "scheduled" if name in active else "retire candidate")
            if node["status"] == "retire candidate":
                node["wave"] = 6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="sfx-sfg1120-before")
    parser.add_argument("--port", type=int, default=54985)
    parser.add_argument("--spark-port", type=int, default=55432)
    parser.add_argument("--spark-retries", type=Path, help="Optional TSV of retried Spark job and status")
    parser.add_argument("--source-ref", default="origin/demo-snowflake-dw-exit")
    args = parser.parse_args()
    ref = subprocess.check_output(["git", "rev-parse", args.source_ref], cwd=ROOT, text=True).strip()
    subprocess.run(["git", "diff", "--exit-code", ref, "--", "warehouse/teradata",
                    "etl/informatica", "etl/spark", "consumers/registry.yaml"], cwd=ROOT, check=True)
    activity, catalog, installed, totals, spark_tables = database(args.port, args.spark_port)
    graph = Inventory()
    warehouse = graph.warehouse()
    if warehouse != catalog or warehouse != installed:
        raise ValueError(f"Warehouse coverage gap: DBC={sorted(warehouse.items() ^ catalog.items())}; "
                         f"emulator={sorted(warehouse.items() ^ installed.items())}")
    graph.powercenter(PC / "infa_shared" / args.namespace / "REP_SESS_LOG.psv")
    spark_run = (SPARK / ".data" / args.namespace / "logs/status.tsv").read_text().splitlines()[1:]
    statuses = dict(line.split()[:2] for line in spark_run if line.strip())
    history = json.loads((SPARK / "history/baseline.json").read_text())["jobs"]
    retries = dict(line.split() for line in args.spark_retries.read_text().splitlines()) if args.spark_retries else {}
    spark_outputs = graph.spark(statuses, history, retries)
    actual = {row["name"] for row in spark_tables}
    if actual != spark_outputs:
        raise ValueError(f"Spark JDBC coverage gap: {sorted(actual ^ spark_outputs)}")
    graph.assess(activity, warehouse)
    result = {
        "tag": "sfg1120", "source_commit": ref, "namespace": args.namespace,
        "dbql_window": {"start": START, "end": END, **totals},
        "objects": sorted((n for n in graph.nodes.values() if "status" in n),
                          key=lambda n: (n["subject_area"], n["kind"], n["name"])),
        "context": sorted((n for n in graph.nodes.values() if "status" not in n), key=lambda n: n["name"]),
        "edges": [dict(source=src, target=dst, relationship=kind) for src, dst, kind in sorted(graph.edges)],
    }
    # One JSON line per item keeps the snapshot reviewable without repeating indented field names.
    scalar = {k: v for k, v in result.items() if k not in ("objects", "context", "edges")}
    blocks = [json.dumps(scalar, indent=2)[:-2]]
    for key in ("objects", "context", "edges"):
        blocks.append(f'  "{key}": [\n' + ",\n".join(
            "    " + json.dumps(row, default=str) for row in result[key]
        ) + "\n  ]")
    (HERE / "manifest.json").write_text(",\n".join(blocks) + "\n}\n")
    print(Counter(node["kind"] for node in result["objects"]))
    print(Counter(node["status"] for node in result["objects"]))


if __name__ == "__main__":
    main()
