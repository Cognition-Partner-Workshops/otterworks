"""Consumption attribution for OtterWorks workloads on Snowflake.

Every connection, task and Streamlit app a workload runs is labeled so the
monthly bill can be split by client-side ID (csid), workload, commit and phase.
The rules live in workloads/attribution/README.md; this module is the only
place that builds the names and the tag, so every session labels the same way.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

RUN_TOKEN = "SFNFR_20261104"
APPLICATION = "Devin_Demo"
PHASES = ("dev", "runtime")
GOVERNANCE_DATABASE = f"{RUN_TOKEN}_GOVERNANCE"
TAG_FQN = f"{GOVERNANCE_DATABASE}.TAGS.DEVIN_CSID"
EMAIL_MASKING_POLICY = f"{GOVERNANCE_DATABASE}.POLICIES.CUSTOMER_EMAIL_MASK"
MIGRATIONS_WAREHOUSE = f"{RUN_TOKEN}_WH_MIGRATIONS"
ACCESS_ROLES = ("reader", "analyst")
WAREHOUSE_SIZE = "XSMALL"
AUTO_SUSPEND_SECONDS = 60
MONTHLY_CREDIT_QUOTA = 10
ANALYTICS_SCHEMA = "ANALYTICS"
QUERY_TAG_MAX_CHARS = 2000
PENDING = "pending"

IDENT_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
CSID_RE = re.compile(r"^cs_[a-z][a-z0-9]*(_[a-z0-9]+)*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9]*_[0-9]{8}$")
RUN_ID_RE = re.compile(r"^(?P<token>[A-Z][A-Z0-9]*_[0-9]{8})-[A-Za-z0-9_.:-]+$")
SESSION_URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+/sessions/[0-9a-f]{32}$")


class AttributionError(ValueError):
    """A label would break the attribution rules."""


def _identifier(kind: str, value: str) -> str:
    if not isinstance(value, str) or not IDENT_RE.match(value):
        raise AttributionError(f"{kind} must be lower snake_case, got {value!r}")
    return value


def csid(workload: str, endpoint: str) -> str:
    return f"cs_{_identifier('workload', workload)}_{_identifier('endpoint', endpoint)}"


def service_user(client_side_id: str) -> str:
    if not CSID_RE.match(client_side_id):
        raise AttributionError(f"not a client-side ID: {client_side_id!r}")
    return f"{RUN_TOKEN}_SVC_{client_side_id.upper()}"


def warehouse_name(workload: str) -> str:
    return f"{RUN_TOKEN}_WH_{_identifier('workload', workload).upper()}"


def resource_monitor_name(workload: str) -> str:
    return f"{RUN_TOKEN}_RM_{_identifier('workload', workload).upper()}"


def role_name(access: str) -> str:
    if access not in ACCESS_ROLES:
        raise AttributionError(f"access role must be one of {ACCESS_ROLES}, got {access!r}")
    return f"{RUN_TOKEN}_{access.upper()}"


def database_name(workload: str) -> str:
    return f"{RUN_TOKEN}_DB_{_identifier('workload', workload).upper()}"


def output_table_name(workload: str) -> str:
    return f"{database_name(workload)}.{ANALYTICS_SCHEMA}.{workload.upper()}"


def task_name(workload: str) -> str:
    return f"{database_name(workload)}.{ANALYTICS_SCHEMA}.REFRESH_{workload.upper()}"


def streamlit_name(workload: str) -> str:
    return f"{database_name(workload)}.{ANALYTICS_SCHEMA}.{workload.upper()}_APP"


def devin_csid_value(csids: list[str] | tuple[str, ...]) -> str:
    """DEVIN_CSID value for an object a whole workload owns: its csids, sorted, comma-joined."""
    if not csids:
        raise AttributionError("an object tag needs at least one csid")
    for c in csids:
        if not CSID_RE.match(c):
            raise AttributionError(f"not a client-side ID: {c!r}")
    return ",".join(sorted(set(csids)))


@dataclass(frozen=True)
class Endpoint:
    workload: str
    endpoint: str

    def __post_init__(self) -> None:
        _identifier("workload", self.workload)
        _identifier("endpoint", self.endpoint)

    @classmethod
    def from_csid(cls, client_side_id: str, workload: str) -> Endpoint:
        prefix = f"cs_{workload}_"
        if not client_side_id.startswith(prefix) or len(client_side_id) == len(prefix):
            raise AttributionError(f"{client_side_id!r} is not an endpoint of workload {workload!r}")
        return cls(workload, client_side_id[len(prefix) :])

    @property
    def csid(self) -> str:
        return csid(self.workload, self.endpoint)

    @property
    def service_user(self) -> str:
        return service_user(self.csid)

    @property
    def warehouse(self) -> str:
        return warehouse_name(self.workload)

    @property
    def database(self) -> str:
        return database_name(self.workload)


def make_run_id(workload: str, phase: str, when: datetime | None = None, run_token: str = RUN_TOKEN) -> str:
    """<RUN_TOKEN>-<workload>-<phase>-<UTC yyyymmddThhmmssZ>."""
    _check_phase(phase)
    _identifier("workload", workload)
    if not RUN_TOKEN_RE.match(run_token):
        raise AttributionError(f"run token must look like SFNFR_20261104, got {run_token!r}")
    when = (when or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return f"{run_token}-{workload}-{phase}-{when.strftime('%Y%m%dT%H%M%SZ')}"


def _check_phase(phase: str) -> None:
    if phase not in PHASES:
        raise AttributionError(f"phase must be one of {PHASES}, got {phase!r}")


def query_tag(
    endpoint: Endpoint,
    *,
    phase: str,
    commit: str,
    run_id: str,
    session_url: str | None = None,
) -> dict[str, str]:
    """The QUERY_TAG object, in a fixed key order. session_url is required for dev and refused for runtime."""
    _check_phase(phase)
    if not isinstance(commit, str) or not COMMIT_RE.match(commit):
        raise AttributionError(f"commit must be a full 40-character lower-case SHA, got {commit!r}")
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        raise AttributionError(f"run_id must start with a run token such as {RUN_TOKEN}-, got {run_id!r}")
    tag = {
        "csid": endpoint.csid,
        "workload": endpoint.workload,
        "phase": phase,
        "commit": commit,
        "run_id": run_id,
    }
    if phase == "dev":
        if not session_url or not SESSION_URL_RE.match(session_url):
            raise AttributionError(f"phase dev needs the Devin session URL, got {session_url!r}")
        tag["session_url"] = session_url
    elif session_url is not None:
        raise AttributionError("phase runtime must not carry a session URL")
    return tag


def query_tag_json(endpoint: Endpoint, **kwargs: Any) -> str:
    text = json.dumps(query_tag(endpoint, **kwargs), separators=(",", ":"))
    if len(text) > QUERY_TAG_MAX_CHARS:
        raise AttributionError(f"QUERY_TAG is {len(text)} characters, Snowflake allows {QUERY_TAG_MAX_CHARS}")
    return text


def sql_string(value: str) -> str:
    """A single-quoted Snowflake string literal."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def connection_params(
    endpoint: Endpoint,
    *,
    account: str,
    private_key_file: str,
    phase: str,
    commit: str,
    run_id: str,
    session_url: str | None = None,
    role: str | None = None,
    schema: str = ANALYTICS_SCHEMA,
    private_key_file_pwd: str | None = None,
) -> dict[str, Any]:
    """Keyword arguments for snowflake.connector.connect() for one endpoint."""
    if not account:
        raise AttributionError("account is required")
    if not private_key_file:
        raise AttributionError("endpoints authenticate with a key pair; private_key_file is required")
    params: dict[str, Any] = {
        "account": account,
        "user": endpoint.service_user,
        "authenticator": "SNOWFLAKE_JWT",
        "private_key_file": private_key_file,
        "application": APPLICATION,
        "warehouse": endpoint.warehouse,
        "database": endpoint.database,
        "schema": schema,
        "session_parameters": {
            "QUERY_TAG": query_tag_json(endpoint, phase=phase, commit=commit, run_id=run_id, session_url=session_url),
        },
    }
    if role:
        params["role"] = role
    if private_key_file_pwd:
        params["private_key_file_pwd"] = private_key_file_pwd
    return params


def connect(endpoint: Endpoint, **kwargs: Any):
    import snowflake.connector  # imported lazily so the helper and its tests need no connector

    return snowflake.connector.connect(**connection_params(endpoint, **kwargs))


def create_task_sql(
    endpoint: Endpoint,
    *,
    schedule: str,
    body: str,
    commit: str,
    run_id: str,
    phase: str = "runtime",
    session_url: str | None = None,
) -> str:
    """CREATE TASK with the tag on the task itself: a task run does not inherit the creating session's tag."""
    tag = query_tag_json(endpoint, phase=phase, commit=commit, run_id=run_id, session_url=session_url)
    return (
        f"CREATE OR REPLACE TASK {task_name(endpoint.workload)}\n"
        f"  WAREHOUSE = {endpoint.warehouse}\n"
        f"  SCHEDULE = {sql_string(schedule)}\n"
        f"  QUERY_TAG = {sql_string(tag)}\n"
        f"AS\n{body}"
    )


def alter_task_query_tag_sql(endpoint: Endpoint, **kwargs: Any) -> str:
    kwargs.setdefault("phase", "runtime")
    return f"ALTER TASK {task_name(endpoint.workload)} SET QUERY_TAG = {sql_string(query_tag_json(endpoint, **kwargs))}"


def streamlit_query_tag_sql(endpoint: Endpoint, **kwargs: Any) -> str:
    """First statement a Streamlit app runs on its session, since it has no client connection to configure."""
    kwargs.setdefault("phase", "runtime")
    return f"ALTER SESSION SET QUERY_TAG = {sql_string(query_tag_json(endpoint, **kwargs))}"


def warehouse_ddl(workload: str, *, credit_quota: int = MONTHLY_CREDIT_QUOTA) -> list[str]:
    if not isinstance(credit_quota, int) or credit_quota <= 0:
        raise AttributionError("credit_quota must be a positive integer")
    monitor, warehouse = resource_monitor_name(workload), warehouse_name(workload)
    return [
        f"CREATE RESOURCE MONITOR IF NOT EXISTS {monitor} WITH CREDIT_QUOTA = {credit_quota} "
        "FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY "
        "TRIGGERS ON 75 PERCENT DO NOTIFY ON 100 PERCENT DO SUSPEND ON 110 PERCENT DO SUSPEND_IMMEDIATE",
        f"CREATE WAREHOUSE IF NOT EXISTS {warehouse} WITH WAREHOUSE_SIZE = '{WAREHOUSE_SIZE}' "
        f"AUTO_SUSPEND = {AUTO_SUSPEND_SECONDS} AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE "
        f"RESOURCE_MONITOR = {monitor}",
    ]


def service_user_ddl(endpoint: Endpoint, *, rsa_public_key: str, role: str | None = None) -> str:
    key = "".join(line for line in rsa_public_key.strip().splitlines() if not line.startswith("-----"))
    if not key:
        raise AttributionError("rsa_public_key is empty")
    parts = [
        f"CREATE USER IF NOT EXISTS {endpoint.service_user} TYPE = SERVICE",
        f"RSA_PUBLIC_KEY = {sql_string(key)}",
        f"DEFAULT_WAREHOUSE = {endpoint.warehouse}",
    ]
    if role:
        parts.append(f"DEFAULT_ROLE = {role}")
    parts.append(f"COMMENT = {sql_string(f'Key-pair service user for {endpoint.csid}')}")
    return " ".join(parts)


def object_tag_ddl(workload: str, csids: list[str], *, task: bool = True, streamlit: bool = False) -> list[str]:
    value = sql_string(devin_csid_value(csids))
    statements = [
        f"ALTER WAREHOUSE {warehouse_name(workload)} SET TAG {TAG_FQN} = {value}",
        f"ALTER DATABASE {database_name(workload)} SET TAG {TAG_FQN} = {value}",
    ]
    if task:
        statements.append(f"ALTER TASK {task_name(workload)} SET TAG {TAG_FQN} = {value}")
    if streamlit:
        statements.append(f"ALTER STREAMLIT {streamlit_name(workload)} SET TAG {TAG_FQN} = {value}")
    return statements


def current_commit(repo: str = ".") -> str:
    return subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def names(workloads: list[str] | tuple[str, ...]) -> dict[str, str]:
    """Every object name the foundation migrations use, as schemachange Jinja vars."""
    out = {
        "run_token": RUN_TOKEN,
        "governance_db": GOVERNANCE_DATABASE,
        "tag_fqn": TAG_FQN,
        "email_masking_policy": EMAIL_MASKING_POLICY,
        "migrations_wh": MIGRATIONS_WAREHOUSE,
        "migrations_rm": f"{RUN_TOKEN}_RM_MIGRATIONS",
    }
    out.update({f"{access}_role": role_name(access) for access in ACCESS_ROLES})
    for workload in workloads:
        out[f"db_{workload}"] = database_name(workload)
        out[f"wh_{workload}"] = warehouse_name(workload)
        out[f"rm_{workload}"] = resource_monitor_name(workload)
        out[f"stage_{workload}"] = f"{database_name(workload)}.RAW.POSTGRES_FILES"
        out[f"format_{workload}"] = f"{database_name(workload)}.RAW.POSTGRES_CSV"
        out[f"history_{workload}"] = f"{GOVERNANCE_DATABASE}.SCHEMACHANGE.PIPELINE_{workload.upper()}"
        out[f"dbt_project_{workload}"] = f"{database_name(workload)}.ANALYTICS.OTTERWORKS_DBT"
        out[f"dbt_stage_{workload}"] = f"{database_name(workload)}.ANALYTICS.DBT_SOURCE_FILES"
        out[f"proof_schema_{workload}"] = f"{database_name(workload)}.PIPELINE_FRESH_PROOF"
        out[f"proof_history_{workload}"] = f"{database_name(workload)}.PIPELINE_FRESH_PROOF.CHANGE_HISTORY"
        out[f"ops_schema_{workload}"] = f"{database_name(workload)}.OPS"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    tag = sub.add_parser("tag", help="print the QUERY_TAG JSON for an endpoint")
    tag.add_argument("--csid", required=True)
    tag.add_argument("--workload", required=True)
    tag.add_argument("--phase", required=True, choices=PHASES)
    tag.add_argument("--commit")
    tag.add_argument("--run-id")
    tag.add_argument("--session-url")
    ddl = sub.add_parser("ddl", help="print warehouse, monitor and object-tag DDL for a workload")
    ddl.add_argument("--workload", required=True)
    ddl.add_argument("--csid", action="append", required=True)
    ddl.add_argument("--streamlit", action="store_true")
    names_cmd = sub.add_parser("names", help="print the foundation object names as JSON (schemachange --vars)")
    names_cmd.add_argument("--workload", action="append", required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "tag":
            endpoint = Endpoint.from_csid(args.csid, args.workload)
            print(
                query_tag_json(
                    endpoint,
                    phase=args.phase,
                    commit=args.commit or current_commit(),
                    run_id=args.run_id or make_run_id(args.workload, args.phase),
                    session_url=args.session_url,
                )
            )
        elif args.cmd == "names":
            print(json.dumps(names(args.workload), separators=(",", ":")))
        else:
            for statement in warehouse_ddl(args.workload) + object_tag_ddl(
                args.workload, args.csid, streamlit=args.streamlit
            ):
                print(statement + ";")
    except AttributionError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
