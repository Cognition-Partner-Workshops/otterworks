"""Check the ETL Airflow Connections and Variables (etl/airflow/CONFIG.md).

static  (repo root, stdlib only): .env.example and CONFIG.md declare the same Connections and
        Variables with the same values, each script default CONFIG.md maps is still in that
        etl/scripts file with that value, the decided defaults hold, and no credential from
        etl/config.ini is in etl/airflow/ or docker-compose.airflow.yml.
live    (inside an Airflow container, script on stdin): every Connection and every Variable in
        VARIABLES resolves, then probe the services passed to --probe (postgres, localstack,
        meilisearch). The localstack probe also checks that every bucket, queue and table a
        Variable names exists.
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
# Required Variable keys; static keeps .env.example and CONFIG.md equal to this list.
VARIABLES = (
    "data_lake_bucket",
    "file_storage_bucket",
    "quarantine_bucket",
    "archive_bucket",
    "analytics_prefix",
    "analytics_report_prefix",
    "analytics_report_top_users",
    "analytics_sqs_queue_name",
    "analytics_sqs_max_messages",
    "analytics_sqs_batch_size",
    "analytics_sqs_wait_time_seconds",
    "analytics_sqs_max_consecutive_errors",
    "analytics_dynamodb_table",
    "audit_archive_dynamodb_table",
    "audit_archive_retention_days",
    "audit_archive_s3_prefix",
    "audit_archive_storage_class",
    "audit_archive_report_prefix",
    "audit_archive_delete_batch_size",
    "audit_archive_delete_enabled",
    "search_reindex_documents_index",
    "search_reindex_files_index",
    "search_reindex_api_page_size",
    "search_reindex_bulk_batch_size",
    "search_reindex_task_timeout_seconds",
    "search_reindex_bulk_task_timeout_seconds",
    "storage_cleanup_files_prefix",
    "storage_cleanup_metadata_table",
    "storage_cleanup_quarantine_prefix",
    "storage_cleanup_report_prefix",
    "storage_cleanup_price_per_gb_month_usd",
    "storage_cleanup_normalize_keys",
    "user_activity_lookback_days",
    "user_activity_report_prefix",
    "user_activity_max_user_summaries",
    "user_activity_top_users",
)
DECIDED_DEFAULTS = {
    "audit_archive_delete_enabled": False,
    "storage_cleanup_normalize_keys": False,
}
# Variables that name a LocalStack resource, by key suffix.
RESOURCE_SUFFIXES = {"_bucket": "s3", "_queue_name": "sqs", "_table": "dynamodb"}
# scripts/localstack-init.sh does not create every one of them; the golden harness does.
CREATE_RESOURCES_HINT = (
    "scripts/localstack-init.sh does not create these. Create them (wipes nothing) with the ETL "
    "golden harness: cd etl/tests/golden && uv run --python 3.11 --with-requirements "
    'requirements.txt python -c "from harness import infra; infra.wait_ready(); '
    'infra.ensure_resources()" (what `make legacy-cron-up` runs, PR #1909). '
    "Not `make etl-golden`: it resets the local stack"
)
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


def legacy_mappings(config_md: str) -> list[tuple[str, str, str, str]]:
    """(key, script, legacy snippet, local value) for CONFIG.md rows that map a script value."""
    section = config_md.split("## Variables", 1)[1].split("\n## ", 1)[0]
    rows, script = [], None
    for line in section.splitlines():
        if line.startswith("### "):
            found = re.search(r"\(`([a-z_]+\.py)`\)", line)
            script = found.group(1) if found else None
            continue
        row = re.match(r"^\| `([a-z0-9_]+)` \| (.*?) \| `([^`]*)` \|$", line)
        snippet = re.search(r"`([^`]+)`", row.group(2)) if row else None
        if script and row and snippet and not row.group(2).startswith(("*new*", "`[s3]")):
            rows.append((row.group(1), script, snippet.group(1), row.group(3)))
    return rows


def check_legacy(root: Path, config_md: str, variables: dict[str, str]) -> tuple[list[str], int]:
    errors = []
    mappings = legacy_mappings(config_md)
    for key, script, snippet, local in mappings:
        if variables.get(key) != local:
            errors.append(
                f"{key}: CONFIG.md value {local!r} != .env.example {variables.get(key)!r}"
            )
        source = (root / "etl" / "scripts" / script).read_text()
        if "=" in snippet:
            legacy = snippet.split("=", 1)[1].strip().strip("\"'")
            if snippet not in source:
                errors.append(f"{key}: `{snippet}` no longer in etl/scripts/{script}")
            elif legacy != local:
                errors.append(f"{key}: etl/scripts/{script} has {legacy!r}, mapped to {local!r}")
        elif not token(snippet).search(source):
            errors.append(f"{key}: `{snippet}` no longer in etl/scripts/{script}")
    return errors, len(mappings)


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

    if set(variables) != set(VARIABLES):
        errors.append(
            f".env.example Variables: missing {sorted(set(VARIABLES) - set(variables))}, "
            f"not in VARIABLES {sorted(set(variables) - set(VARIABLES))}"
        )
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

    legacy_errors, legacy_count = check_legacy(root, config_md, variables)
    errors += legacy_errors

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
        f"static: {len(conns)} Connections, {len(variables)} Variables "
        f"({legacy_count} checked against etl/scripts), "
        f"{len(scanned)} files scanned for etl/config.ini credentials"
    )
    return errors


def check_live(probes: list[str]) -> list[str]:
    from airflow.hooks.base import BaseHook
    from airflow.models import Variable

    errors = []
    for conn_id in CONNECTIONS:
        try:
            conn = BaseHook.get_connection(conn_id)
            where = conn.extra_dejson.get("endpoint_url") or f"{conn.host}:{conn.port}"
            print(f"connection {conn_id}: {conn.conn_type} {where}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"connection {conn_id}: {exc}")
    for key in VARIABLES:
        raw = Variable.get(key, default_var=None)
        if raw is None:
            errors.append(
                f"variable {key}: not set (add AIRFLOW_VAR_{key.upper()} from .env.example "
                "to etl/airflow/.env, then `make airflow-up`)"
            )
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        print(f"variable {key} = {json.dumps(value)}")
    unknown = sorted(
        k.removeprefix("AIRFLOW_VAR_").lower()
        for k in os.environ
        if k.startswith("AIRFLOW_VAR_") and k.removeprefix("AIRFLOW_VAR_").lower() not in VARIABLES
    )
    if unknown:
        print(f"note: Variables set but not in VARIABLES: {unknown}")
    for key, default in DECIDED_DEFAULTS.items():
        value = Variable.get(key, default_var=None)
        if value is not None and json.loads(value) is not default:
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
    from airflow.models import Variable
    from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook
    from botocore.exceptions import ClientError

    clients = {
        kind: AwsBaseHook(aws_conn_id="aws_default", client_type=kind).get_conn()
        for kind in set(RESOURCE_SUFFIXES.values())
    }
    exists = {
        "s3": lambda name: clients["s3"].head_bucket(Bucket=name),
        "sqs": lambda name: clients["sqs"].get_queue_url(QueueName=name),
        "dynamodb": lambda name: clients["dynamodb"].describe_table(TableName=name),
    }
    named = sorted(
        (kind, Variable.get(key))
        for key in VARIABLES
        for suffix, kind in RESOURCE_SUFFIXES.items()
        if key.endswith(suffix)
    )
    missing = []
    for kind, name in named:
        try:
            exists[kind](name)
        except ClientError:
            missing.append(f"{kind}:{name}")
    if missing:
        raise RuntimeError(f"missing {missing}: {CREATE_RESOURCES_HINT}")
    return f"{clients['s3'].meta.endpoint_url}: {len(named)} named buckets/queues/tables exist"


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
