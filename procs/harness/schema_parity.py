"""Replay the recorded legacy billing scenarios directly against a database.

`make procs-parity` grades the extracted Python service over HTTP. This script
instead proves that a rebuilt *legacy* database (for example one built by
services/legacy-billing/db/migrate.sh rather than schema.sql) still produces
the immutable transcripts: every scenario of every module is re-run through
the stored procedure and its business fields and state probes must equal the
recording. Transcripts are only read, never written.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg
import yaml

try:
    from procs.harness import record
    from procs.harness.fingerprints import fixture_sha, source_sha
except ModuleNotFoundError:
    import record
    from fingerprints import fixture_sha, source_sha

ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTS = ROOT / "procs" / "transcripts"
ROUTES = ROOT / "procs" / "routes.yaml"
REPORT_DIR = ROOT / "procs" / "reports"
DB_DIR = ROOT / "services" / "legacy-billing" / "db"
MIGRATION_SOURCES = {
    "0001_billing_schema.sql": "schema.sql",
    "0002_plans.sql": "procs/plans.sql",
    "0003_rating.sql": "procs/rating.sql",
    "0004_invoicing.sql": "procs/invoicing.sql",
    "0005_dunning.sql": "procs/dunning.sql",
}
SEED_QUIRK = {
    "description": (
        "sp_finalize_rating for the three periods seed.sql already holds for tenant 1 "
        "with literal ids; the procedure derives md5(tenant || period_start), keeps the "
        "seeded id on conflict and the rating_results insert fails"
    ),
    "periods": [("2025-11-01", "2025-11-30"), ("2025-12-01", "2025-12-31"), ("2026-01-01", "2026-01-31")],
    "sql": "CALL billing.sp_finalize_rating('00000000-0000-0000-0000-000000000001', %s, %s)",
}

FAIL = 1
UNREACHABLE = 3
IDENTITY_INVALID = 5
COVERAGE_MISSING = 6
SOURCE_MISMATCH = 7
RESET_FAILED = 8


def connect() -> psycopg.Connection:
    sslmode = os.getenv("DB_SSLMODE", "prefer")
    options: dict[str, Any] = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", f"billing_{os.getenv('NS', 'dev')}"),
        "user": os.getenv("DB_USER", "billing"),
        "password": os.getenv("DB_PASSWORD", "billing"),
        "sslmode": sslmode,
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    }
    # Same rule as legacy-billing db_connect(): a root cert only with verify-*.
    if sslmode in {"verify-ca", "verify-full"} and os.getenv("DB_SSLROOTCERT"):
        options["sslrootcert"] = os.environ["DB_SSLROOTCERT"]
    return psycopg.connect(**options)


def connection_identity(connection: psycopg.Connection) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT current_user, r.rolsuper, s.ssl, s.version, current_setting('server_version'),
                   current_setting('search_path'), current_setting('TimeZone')
            FROM pg_roles AS r, pg_stat_ssl AS s
            WHERE r.rolname = current_user AND s.pid = pg_backend_pid()
            """
        )
        user, superuser, ssl, tls_version, server_version, search_path, timezone = cursor.fetchone()
    connection.rollback()
    return {
        "current_user": user,
        "rolsuper": superuser,
        "ssl": ssl,
        "tls_version": tls_version,
        "server_version": server_version,
        "search_path": search_path,
        "timezone": timezone,
        "sslmode": os.getenv("DB_SSLMODE", "prefer"),
    }


def identity_errors(identity: dict[str, Any], expect_user: str | None, require_tls: bool) -> list[str]:
    errors = []
    if expect_user and identity["current_user"] != expect_user:
        errors.append(f"connected as {identity['current_user']}, expected {expect_user}")
    if expect_user and identity["rolsuper"]:
        errors.append(f"{identity['current_user']} is a superuser")
    if require_tls and not identity["ssl"]:
        errors.append("connection is not using TLS")
    return errors


def migration_drift() -> list[str]:
    errors = []
    for migration, source in MIGRATION_SOURCES.items():
        migration_path = DB_DIR / "migrations" / migration
        source_path = DB_DIR / source
        if not migration_path.exists():
            errors.append(f"migration {migration} is missing")
        elif migration_path.read_bytes() != source_path.read_bytes():
            errors.append(f"migration {migration} differs from {source} (recordings came from {source})")
    return errors


def expected_modules() -> list[str]:
    modules = set(yaml.safe_load(ROUTES.read_text())["modules"])
    modules.update(path.name for path in record.SCENARIOS.iterdir() if path.is_dir())
    return sorted(modules)


def load_pairs(module: str | None, scenario_id: str | None) -> tuple[list[tuple[dict, dict]], list[str]]:
    scenarios = {item["id"]: item for item in record.load_scenarios(module)}
    transcripts = {
        item["scenario"]: item
        for item in (
            json.loads(path.read_text())
            for path in sorted(TRANSCRIPTS.glob(f"{module}/*.json" if module else "*/*.json"))
        )
    }
    missing = [f"{sid}: scenario has no transcript" for sid in sorted(set(scenarios) - set(transcripts))]
    missing += [f"{sid}: transcript has no scenario" for sid in sorted(set(transcripts) - set(scenarios))]
    modules = [module] if module else expected_modules()
    for name in modules:
        if not any(item["module"] == name for item in transcripts.values()):
            missing.append(f"{name}: module has no recorded transcripts")
    pairs = [
        (scenarios[sid], transcripts[sid])
        for sid in sorted(set(scenarios) & set(transcripts), key=lambda sid: (scenarios[sid]["module"], sid))
        if scenario_id is None or sid == scenario_id
    ]
    return pairs, missing


def differences(transcript: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for key in ("entrypoint", "inputs"):
        if transcript.get(key) != actual.get(key):
            found.append({"kind": key, "name": key, "expected": transcript.get(key), "actual": actual.get(key)})
    for kind, key in (("field", "business_fields"), ("probe", "probes")):
        expected_values = transcript.get(key, {})
        actual_values = actual.get(key, {})
        for name in sorted(set(expected_values) | set(actual_values)):
            expected = expected_values.get(name, "<absent>")
            got = actual_values.get(name, "<absent>")
            if expected != got:
                found.append({"kind": kind, "name": name, "expected": expected, "actual": got})
    return found


def reset(connection: psycopg.Connection | None, reset_command: str | None) -> None:
    if reset_command:
        completed = subprocess.run(reset_command, shell=True, capture_output=True, text=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"reset command failed ({completed.returncode}): {completed.stderr or completed.stdout}")
    else:
        record.reset_database(connection)


def seed_quirk(connection: psycopg.Connection) -> dict[str, Any]:
    outcomes = []
    for period_start, period_end in SEED_QUIRK["periods"]:
        outcome: dict[str, Any] = {"period_start": period_start, "raised": False, "sqlstate": None, "error": None}
        try:
            with connection.cursor() as cursor:
                cursor.execute(SEED_QUIRK["sql"], (period_start, period_end))
        except psycopg.Error as error:
            outcome.update(raised=True, sqlstate=error.sqlstate, error=str(error).splitlines()[0])
        connection.rollback()
        outcomes.append(outcome)
    return {"description": SEED_QUIRK["description"], "sql": SEED_QUIRK["sql"], "outcomes": outcomes}


def write_report(report_dir: Path, report: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    label = report["label"]
    (report_dir / f"schema-parity-{label}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    identity = report.get("identity") or {}
    lines = [
        f"# Legacy billing schema parity: {label}",
        "",
        f"Source SHA: `{report['source_sha']}`",
        f"Fixture SHA: `{report['fixture_sha']}`",
        f"Connection: user `{identity.get('current_user')}` rolsuper={identity.get('rolsuper')} "
        f"ssl={identity.get('ssl')} {identity.get('tls_version') or ''} sslmode={identity.get('sslmode')} "
        f"server {identity.get('server_version')} search_path=`{identity.get('search_path')}` "
        f"TimeZone={identity.get('timezone')}",
        "",
        "| Module | Scenarios | PASS | FAIL |",
        "| --- | --- | --- | --- |",
    ]
    for module, counts in sorted(report["modules"].items()):
        lines.append(f"| {module} | {counts['total']} | {counts['PASS']} | {counts['FAIL']} |")
    lines.append("")
    for item in report["results"]:
        lines.append(f"- **{item['status']}** `{item['module']}/{item['scenario']}`")
        if item.get("error"):
            lines.append(f"  - error: {item['error']}")
        for diff in item.get("differences", []):
            lines.append(
                f"  - {diff['kind']} `{diff['name']}`: expected `{diff['expected']}`, actual `{diff['actual']}`"
            )
    lines.extend(f"- Error: {error}" for error in report["errors"])
    quirk = report.get("seed_quirk")
    if quirk:
        lines.extend(["", f"Known seed quirk, not graded as a migration difference: {quirk['description']}.", ""])
        lines.extend(
            f"- tenant 1 {item['period_start']}: raised={item['raised']} sqlstate={item['sqlstate']}: {item['error']}"
            for item in quirk["outcomes"]
        )
        if "matches_baseline" in quirk:
            lines.append(f"- identical to the original schema.sql baseline: {quirk['matches_baseline']}")
    lines.extend(["", f"Result: **{report['verdict']}**"])
    (report_dir / f"schema-parity-{label}.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module")
    parser.add_argument("--scenario")
    parser.add_argument("--label", default=os.getenv("PROCS_SCHEMA_LABEL", "original"))
    parser.add_argument(
        "--reset-command",
        default=os.getenv("PROCS_SCHEMA_RESET_COMMAND"),
        help="shell command that rebuilds the database before each scenario; "
        "without it the schema.sql reset from record.py is used",
    )
    parser.add_argument("--expect-user", default=os.getenv("PROCS_SCHEMA_EXPECT_USER"))
    parser.add_argument("--require-tls", action="store_true", default=os.getenv("PROCS_SCHEMA_REQUIRE_TLS") == "1")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument(
        "--baseline-report",
        type=Path,
        help="schema-parity JSON from the original schema.sql database; the seed-quirk "
        "outcomes must be identical, so the quirk is shown to predate the migration",
    )
    args = parser.parse_args()

    report: dict[str, Any] = {
        "label": args.label,
        "source_sha": source_sha(),
        "fixture_sha": fixture_sha(),
        "reset": args.reset_command or "record.reset_database (schema.sql + procs + seed)",
        "results": [],
        "modules": {},
        "errors": [],
        "verdict": "FAIL",
    }
    expected_sha = (TRANSCRIPTS / "SOURCE_SHA").read_text().strip()
    expected_fixture = (TRANSCRIPTS / "FIXTURE_SHA").read_text().strip()
    if expected_sha != report["source_sha"]:
        report["errors"].append(f"transcript SOURCE_SHA {expected_sha} != current procs {report['source_sha']}")
    if expected_fixture != report["fixture_sha"]:
        report["errors"].append(f"transcript FIXTURE_SHA {expected_fixture} != current fixture {report['fixture_sha']}")
    report["errors"].extend(migration_drift())
    if report["errors"]:
        write_report(args.report_dir, report)
        print("\n".join(report["errors"]), file=sys.stderr)
        return SOURCE_MISMATCH

    pairs, missing = load_pairs(args.module, args.scenario)
    report["errors"].extend(missing)
    if not pairs:
        report["errors"].append("no scenarios selected")

    try:
        connection = connect()
    except psycopg.Error as error:
        report["errors"].append(f"database unreachable: {error}")
        write_report(args.report_dir, report)
        print(report["errors"][-1], file=sys.stderr)
        return UNREACHABLE
    try:
        report["identity"] = connection_identity(connection)
        bad_identity = identity_errors(report["identity"], args.expect_user, args.require_tls)
        if bad_identity:
            report["errors"].extend(bad_identity)
            write_report(args.report_dir, report)
            print("\n".join(bad_identity), file=sys.stderr)
            return IDENTITY_INVALID
        for scenario, transcript in pairs:
            module = scenario["module"]
            counts = report["modules"].setdefault(module, {"total": 0, "PASS": 0, "FAIL": 0})
            counts["total"] += 1
            try:
                if args.reset_command:
                    connection.close()
                reset(None if args.reset_command else connection, args.reset_command)
                if args.reset_command:
                    connection = connect()
            except (RuntimeError, psycopg.Error) as error:
                report["errors"].append(f"{scenario['id']}: {error}")
                write_report(args.report_dir, report)
                print(report["errors"][-1], file=sys.stderr)
                return RESET_FAILED
            item: dict[str, Any] = {"scenario": scenario["id"], "module": module}
            try:
                actual = record.run_scenario(connection, scenario)
                connection.rollback()
                item["differences"] = differences(transcript, actual)
            except psycopg.Error as error:
                connection.rollback()
                item["differences"] = []
                item["error"] = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            item["status"] = "FAIL" if item["differences"] or item.get("error") else "PASS"
            counts[item["status"]] += 1
            report["results"].append(item)
        if args.module is None and args.scenario is None:
            reset(None if args.reset_command else connection, args.reset_command)
            if args.reset_command:
                connection.close()
                connection = connect()
            report["seed_quirk"] = seed_quirk(connection)
            if args.baseline_report:
                baseline = json.loads(args.baseline_report.read_text()).get("seed_quirk")
                same = baseline is not None and baseline["outcomes"] == report["seed_quirk"]["outcomes"]
                report["seed_quirk"]["matches_baseline"] = same
                if not same:
                    report["errors"].append(f"seed quirk outcomes differ from baseline {args.baseline_report.name}")
    finally:
        connection.close()

    failed = [item for item in report["results"] if item["status"] == "FAIL"]
    report["verdict"] = "PASS" if not failed and not report["errors"] else "FAIL"
    write_report(args.report_dir, report)
    for module, counts in sorted(report["modules"].items()):
        print(f"{args.label} {module}: {counts['PASS']}/{counts['total']} PASS")
    for error in report["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    print(
        f"Schema parity {args.label}: PASS={len(report['results']) - len(failed)} FAIL={len(failed)} "
        f"errors={len(report['errors'])} -> {report['verdict']}"
    )
    if report["errors"]:
        return COVERAGE_MISSING
    return FAIL if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
