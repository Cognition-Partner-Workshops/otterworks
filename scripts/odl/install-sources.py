#!/usr/bin/env python3
import base64
import concurrent.futures
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/odl-sources"))
from odl_sources.generate import Settings

NS = "otterworks-" + os.environ["ODL_TENANT_ID"]
TOKEN = "odl-1795112287"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def ensure_secret(name, data):
    exists = subprocess.check_output(["kubectl", "-n", NS, "get", "secret", name,
                                      "--ignore-not-found", "-o", "jsonpath={.metadata.name}"], text=True)
    if exists:
        return
    obj = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": name, "namespace": NS,
            "labels": {"run_token": TOKEN}}, "type": "Opaque",
           "data": {k: base64.b64encode(v.encode()).decode() for k, v in data.items()}}
    run("kubectl", "create", "-f", "-", input=json.dumps(obj), text=True, stdout=subprocess.DEVNULL)


def main():
    settings = Settings.environment()
    deadline = time.monotonic() + 180
    while subprocess.run(["kubectl", "-n", NS, "get", "limitrange", "tenant-limits"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        if time.monotonic() >= deadline:
            raise RuntimeError("Tenant namespace setup timed out")
        time.sleep(2)
    run("kubectl", "-n", NS, "patch", "resourcequota", "tenant-quota", "--type=merge", "-p",
        json.dumps({"spec": {"hard": {"requests.cpu": "6", "requests.memory": "12Gi",
                                     "limits.cpu": "24", "limits.memory": "28Gi", "pods": "60"}}}))
    ensure_secret("db2-archive-credentials", {"DB2_USER": "db2inst1", "DB2_PASSWORD": secrets.token_urlsafe(24)})
    ensure_secret("odl-oracle", {"ORACLE_USER": "ODL", "ORACLE_PASSWORD": secrets.token_urlsafe(24),
                                  "ORACLE_SYS_PASSWORD": secrets.token_urlsafe(24)})
    ensure_secret("odl-postgres", {"DB_HOST": os.environ["ODL_RDS_HOST"], "DB_PORT": os.environ["ODL_RDS_PORT"],
                                    "DB_NAME": "otterworks_" + os.environ["ODL_TENANT_ID"].replace("-", "_"),
                                    "DB_USER": os.environ["DB_USER"], "DB_PASSWORD": os.environ["DB_PASSWORD"]})
    run("kubectl", "-n", NS, "delete", "job", "odl-seed-db2", "odl-seed-oracle", "odl-seed-crm", "--ignore-not-found")
    db2_values = {"dbName": "ODL", "namespaceToken": os.environ["ODL_TENANT_ID"] + "-" + os.environ["ODL_MODE"],
                  "expires": "2027-02-17T00:00:00Z", "storage": {"mode": "emptyDir"},
                  "terminationGracePeriodSeconds": 10,
                  "initJob": {"enabled": False}, "extraLabels": {"run_token": TOKEN}}
    names = ("seed", "db2_customers", "db2_history", "oracle_accounts", "pg_contacts", "dup_rate")
    source_values = {"settings": {"ODL_" + name.upper(): str(getattr(settings, name)) for name in names}}
    if os.getenv("ODL_SEED_IMAGE"):
        source_values["seedImage"] = os.environ["ODL_SEED_IMAGE"]

    def install(release, chart, values):
        run("helm", "upgrade", "--install", release, str(ROOT / chart), "-n", NS,
            "--labels", "run_token=" + TOKEN, "-f", "-", input=json.dumps(values), text=True)

    with concurrent.futures.ThreadPoolExecutor() as pool:
        futures = [pool.submit(install, "db2-archive", "infrastructure/helm/db2-archive", db2_values),
                   pool.submit(install, "odl-sources", "services/odl-sources/oracle", source_values)]
        for future in futures:
            future.result()
    run("kubectl", "-n", NS, "wait", "--for=condition=complete", "job/odl-seed-db2",
        "job/odl-seed-oracle", "job/odl-seed-crm", "--timeout=540s")
    for source in ("db2", "oracle"):
        run("kubectl", "-n", NS, "patch", "cronjob", "odl-refresh-" + source,
            "--type=merge", "-p", '{"spec":{"suspend":false}}')


if __name__ == "__main__":
    main()
