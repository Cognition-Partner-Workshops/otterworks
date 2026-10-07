"""Check the ETL Airflow Connections and Variables (etl/airflow/CONFIG.md).

static  (repo root, stdlib only): .env.example and CONFIG.md declare the same Connections and
        Variables, the decided defaults hold, and no credential from etl/config.ini is in
        etl/airflow/ or docker-compose.airflow.yml.
live    (inside an Airflow container, script on stdin): every Connection and Variable resolves,
        then probe the services passed to --probe (postgres, localstack, meilisearch).
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import sys
from pathlib import Path

CONNECTIONS = (
    "aws_default",
    "otterworks_postgres",
    "otterworks_meilisearch",
    "otterworks_document_service",
    "otterworks_file_service",
)
DECIDED_DEFAULTS = {
    "audit_archive_delete_enabled": False,
    "storage_cleanup_normalize_keys": False,
}
# config.ini credentials and database identity: none may appear (as a whole token) in the new
# config. Other config.ini values that equal a local-stack value are listed, not failed.
FORBIDDEN_INI_OPTIONS = {
    "aws": ("access_key", "secret_key"),
    "database": ("host", "database", "user", "password"),
    "services": ("meilisearch_api_key",),
}


def parse_env_file(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def prefixed(env: dict[str, str], prefix: str) -> dict[str, str]:
    return {k.removeprefix(prefix).lower(): v for k, v in env.items() if k.startswith(prefix)}


def token(value: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w.-])" + re.escape(value) + r"(?![\w.-])")


def documented(config_md: str, heading: str) -> set[str]:
    section = config_md.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\| `([a-z0-9_]+)` \|", section, re.MULTILINE))


def check_static(root: Path) -> list[str]:
    airflow_dir = root / "etl" / "airflow"
    env = parse_env_file(airflow_dir / ".env.example")
    config_md = (airflow_dir / "CONFIG.md").read_text()
    errors = []

    conns = prefixed(env, "AIRFLOW_CONN_")
    variables = prefixed(env, "AIRFLOW_VAR_")
    other = sorted(k for k in env if not k.startswith(("AIRFLOW_CONN_", "AIRFLOW_VAR_")))
    if other:
        errors.append(f".env.example: keys other than AIRFLOW_CONN_*/AIRFLOW_VAR_*: {other}")

    if set(conns) != set(CONNECTIONS):
        errors.append(f".env.example Connections {sorted(conns)} != expected {sorted(CONNECTIONS)}")
    for conn_id, raw in conns.items():
        try:
            conn = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{conn_id}: not valid JSON ({exc})")
            continue
        if "conn_type" not in conn:
            errors.append(f"{conn_id}: no conn_type")
    aws_extra = json.loads(conns.get("aws_default", "{}")).get("extra", {})
    for key in ("region_name", "endpoint_url"):
        if key not in aws_extra:
            errors.append(f"aws_default: extra.{key} missing")

    for name, missing in (
        ("Connections", set(CONNECTIONS) - documented(config_md, "Connections")),
        ("Variables in CONFIG.md", set(variables) - documented(config_md, "Variables")),
        ("Variables in .env.example", documented(config_md, "Variables") - set(variables)),
    ):
        if missing:
            errors.append(f"{name}: missing {sorted(missing)}")

    for key, default in DECIDED_DEFAULTS.items():
        if key not in variables or json.loads(variables[key]) is not default:
            errors.append(f"{key}: must default to {json.dumps(default)}")

    ini = configparser.ConfigParser()
    ini.read(root / "etl" / "config.ini")
    forbidden = {
        f"{section}.{option}": token(ini.get(section, option))
        for section, options in FORBIDDEN_INI_OPTIONS.items()
        for option in options
        if ini.has_option(section, option) and ini.get(section, option)
    }
    scanned = [p for p in airflow_dir.rglob("*") if p.is_file() and p.name != ".env"]
    scanned.append(root / "docker-compose.airflow.yml")
    for path in scanned:
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for option, pattern in sorted(forbidden.items()):
            if pattern.search(text):
                errors.append(f"{path.relative_to(root)}: contains etl/config.ini {option}")

    example = (airflow_dir / ".env.example").read_text()
    same = sorted(
        f"{section}.{option}"
        for section in ini.sections()
        for option, value in ini.items(section)
        if f"{section}.{option}" not in forbidden and value and token(value).search(example)
    )
    print(f"static: config.ini options equal to a local-stack value (not credentials): {same}")
    print(
        f"static: {len(conns)} Connections, {len(variables)} Variables, "
        f"{len(scanned)} files scanned for etl/config.ini credentials"
    )
    return errors


def check_live(probes: list[str]) -> list[str]:
    from airflow.hooks.base import BaseHook
    from airflow.models import Variable

    errors = []
    expected_vars = sorted(
        k.removeprefix("AIRFLOW_VAR_").lower() for k in os.environ if k.startswith("AIRFLOW_VAR_")
    )
    for conn_id in CONNECTIONS:
        try:
            conn = BaseHook.get_connection(conn_id)
            where = conn.extra_dejson.get("endpoint_url") or f"{conn.host}:{conn.port}"
            print(f"connection {conn_id}: {conn.conn_type} {where}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"connection {conn_id}: {exc}")
    for key in expected_vars:
        raw = Variable.get(key)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        print(f"variable {key} = {json.dumps(value)}")
    for key, default in DECIDED_DEFAULTS.items():
        if key not in expected_vars:
            errors.append(f"variable {key}: not set")
        elif Variable.get(key, deserialize_json=True) is not default:
            print(f"note: {key} overridden from its default {json.dumps(default)}")

    for probe in probes:
        try:
            print(f"probe {probe}: {PROBES[probe]()}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"probe {probe}: {exc}")
    return errors


def probe_postgres() -> str:
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    hook = PostgresHook(postgres_conn_id="otterworks_postgres")
    return hook.get_first("select current_database(), current_user, version()")[2].split(",")[0]


def probe_localstack() -> str:
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    client = S3Hook(aws_conn_id="aws_default").get_conn()
    return f"{client.meta.endpoint_url} ({len(client.list_buckets()['Buckets'])} buckets)"


def probe_meilisearch() -> str:
    from airflow.providers.http.hooks.http import HttpHook

    response = HttpHook(method="GET", http_conn_id="otterworks_meilisearch").run("/health")
    return f"/health {response.status_code} {response.json()}"


PROBES = {
    "postgres": probe_postgres,
    "localstack": probe_localstack,
    "meilisearch": probe_meilisearch,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("static")
    live = sub.add_parser("live")
    live.add_argument("--probe", nargs="*", default=[], choices=sorted(PROBES))
    args = parser.parse_args()

    if args.mode == "static":
        errors = check_static(Path(__file__).resolve().parents[3])
    else:
        errors = check_live(args.probe)
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    print("config check:", "FAILED" if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
