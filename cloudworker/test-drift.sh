#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1 || ! command -v column >/dev/null 2>&1; then
  printf 'cloudworker/test-drift.sh: python3 and column are required\n' >&2
  exit 2
fi

python3 - "$SCRIPT_DIR" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

directory = Path(sys.argv[1])
script = directory / "drift.sh"
fixtures = directory / "testdata" / "drift"
passed = 0
failed = 0


def check(description, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ok   - {description}")
    else:
        failed += 1
        print(f"  FAIL - {description}{': ' + detail if detail else ''}")


def run_fixture(name, json_output=True):
    fixture = fixtures / name
    command = [str(script)]
    if json_output:
        command.append("--json")
    result = subprocess.run(
        command,
        env={**os.environ, "CW_DRIFT_LIVE_FILE": str(fixture)},
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = None
    if json_output and result.returncode < 2:
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return result, parsed


def summary_matches(parsed, *, drift, resources, missing, unowned, checked):
    expected = {
        "drift_attributes": drift,
        "drift_resources": resources,
        "missing": missing,
        "unowned": unowned,
        "checked": checked,
    }
    return parsed is not None and parsed.get("summary") == expected


def drift_rows(parsed):
    return sorted(
        (row["resource"], row["attribute"])
        for row in (parsed or {}).get("rows", [])
        if row["status"] == "DRIFT"
    )


def row_matches(parsed, resource, attribute, *, status, live, git):
    matches = [
        row for row in (parsed or {}).get("rows", [])
        if row["resource"] == resource and row["attribute"] == attribute
    ]
    return (
        len(matches) == 1
        and matches[0].get("status") == status
        and matches[0].get("live") == live
        and matches[0].get("git") == git
        and list(matches[0]) == ["kind", "resource", "attribute", "live", "git", "root", "file_line", "status"]
    )


print("cloudworker drift fixtures")

result, parsed = run_fixture("clean.json")
check("clean fixture exits 0", result.returncode == 0, f"exit {result.returncode}: {result.stderr.strip()}")
check(
    "clean fixture checks all resources with no drift or unowned rows",
    summary_matches(parsed, drift=0, resources=0, missing=0, unowned=[], checked=["sqs", "sns", "dynamodb", "alarm"]),
)
check("clean fixture has only ok rows", parsed is not None and all(row["status"] == "ok" for row in parsed["rows"]))

result, parsed = run_fixture("sqs-retention.json")
check("SQS retention drift exits 1", result.returncode == 1, f"exit {result.returncode}")
check(
    "SQS retention fixture has exactly one drift row",
    drift_rows(parsed) == [("sqs:otterworks-cw-notifications", "MessageRetentionPeriod")],
)
check(
    "SQS retention summary counts one drift resource",
    summary_matches(parsed, drift=1, resources=1, missing=0, unowned=[], checked=["sqs", "sns", "dynamodb", "alarm"]),
)
check(
    "SQS retention row reports exact live and git values",
    row_matches(parsed, "sqs:otterworks-cw-notifications", "MessageRetentionPeriod", status="DRIFT", live="1209600", git="345600"),
)

result, parsed = run_fixture("sns-drift.json")
check("SNS drift exits 1", result.returncode == 1, f"exit {result.returncode}")
check(
    "SNS fixture has exactly the three requested drift rows",
    drift_rows(parsed) == sorted([
        ("sns:otterworks-cw-events", "DeliveryPolicy"),
        ("sns:otterworks-cw-events", "Subscriptions"),
        ("sns-sub:otterworks-cw-events/sqs:otterworks-cw-notifications", "RawMessageDelivery"),
    ]),
)
check(
    "SNS summary counts three attributes on two resources",
    summary_matches(parsed, drift=3, resources=2, missing=0, unowned=[], checked=["sqs", "sns", "dynamodb", "alarm"]),
)
check(
    "SNS topic policy reports exact canonical values",
    row_matches(parsed, "sns:otterworks-cw-events", "DeliveryPolicy", status="DRIFT", live='{"healthyRetryPolicy":{"numRetries":3}}', git="none (default)"),
)
check(
    "SNS subscriptions report the extra https endpoint",
    row_matches(parsed, "sns:otterworks-cw-events", "Subscriptions", status="DRIFT", live="https:https://example.test/hooks,sqs:otterworks-cw-notifications", git="sqs:otterworks-cw-notifications"),
)
check(
    "SNS subscription raw delivery reports exact values",
    row_matches(parsed, "sns-sub:otterworks-cw-events/sqs:otterworks-cw-notifications", "RawMessageDelivery", status="DRIFT", live="true", git="false (default)"),
)

result, parsed = run_fixture("sns-sub-missing.json")
check("missing SNS subscription exits 1", result.returncode == 1, f"exit {result.returncode}")
check(
    "missing SNS subscription reports topic drift and subscription missing",
    drift_rows(parsed) == [("sns:otterworks-cw-events", "Subscriptions")]
    and any(row["resource"] == "sns-sub:otterworks-cw-events/sqs:otterworks-cw-notifications" and row["status"] == "MISSING" for row in parsed["rows"]),
)
check(
    "missing SNS subscription summary counts drift and missing rows",
    summary_matches(parsed, drift=1, resources=1, missing=1, unowned=[], checked=["sqs", "sns", "dynamodb", "alarm"]),
)
check(
    "missing SNS subscription topic row has exact values",
    row_matches(parsed, "sns:otterworks-cw-events", "Subscriptions", status="DRIFT", live="none", git="sqs:otterworks-cw-notifications"),
)

result, parsed = run_fixture("dynamodb-drift.json")
check("DynamoDB drift exits 1", result.returncode == 1, f"exit {result.returncode}")
check(
    "DynamoDB fixture has exactly four drift rows",
    drift_rows(parsed) == sorted([
        ("dynamodb:otterworks-cw-notifications", "BillingMode"),
        ("dynamodb:otterworks-cw-notifications", "TTL"),
        ("dynamodb:otterworks-cw-notifications", "PointInTimeRecovery"),
        ("dynamodb:otterworks-cw-notification-preferences", "KeySchema"),
    ]),
)
check(
    "DynamoDB summary counts four attributes on two resources",
    summary_matches(parsed, drift=4, resources=2, missing=0, unowned=[], checked=["sqs", "sns", "dynamodb", "alarm"]),
)
check(
    "DynamoDB billing mode values are exact",
    row_matches(parsed, "dynamodb:otterworks-cw-notifications", "BillingMode", status="DRIFT", live="PROVISIONED", git="PAY_PER_REQUEST"),
)
check(
    "DynamoDB TTL values are exact",
    row_matches(parsed, "dynamodb:otterworks-cw-notifications", "TTL", status="DRIFT", live="enabled (expiresAt)", git="disabled (default)"),
)
check(
    "DynamoDB preferences key schema values are exact",
    row_matches(parsed, "dynamodb:otterworks-cw-notification-preferences", "KeySchema", status="DRIFT", live="HASH=id:S", git="HASH=userId:S"),
)

result, parsed = run_fixture("alarm-drift.json")
check("alarm drift exits 1", result.returncode == 1, f"exit {result.returncode}")
check(
    "alarm fixture has exactly five drift rows",
    drift_rows(parsed) == sorted([
        ("alarm:otterworks-cw-notifications-dlq-depth", "Metric"),
        ("alarm:otterworks-cw-notifications-dlq-depth", "Period"),
        ("alarm:otterworks-cw-notifications-dlq-depth", "Threshold"),
        ("alarm:otterworks-cw-notifications-dlq-depth", "EvaluationPeriods"),
        ("alarm:otterworks-cw-notifications-dlq-depth", "ActionsEnabled"),
    ]),
)
check(
    "alarm summary counts five attributes on one resource",
    summary_matches(parsed, drift=5, resources=1, missing=0, unowned=[], checked=["sqs", "sns", "dynamodb", "alarm"]),
)
check(
    "alarm threshold is normalized",
    row_matches(parsed, "alarm:otterworks-cw-notifications-dlq-depth", "Threshold", status="DRIFT", live="5", git="1"),
)
check(
    "alarm silencing is flagged despite ignore_changes",
    row_matches(parsed, "alarm:otterworks-cw-notifications-dlq-depth", "ActionsEnabled", status="DRIFT", live="false", git="true (default, ignore_changes)"),
)

result, parsed = run_fixture("missing.json")
check("missing resources exits 1", result.returncode == 1, f"exit {result.returncode}")
check(
    "missing fixture reports alarm and preferences table",
    parsed is not None
    and parsed["summary"]["missing"] == 2
    and sorted((row["kind"], row["resource"], row["status"]) for row in parsed["rows"] if row["status"] == "MISSING")
    == [
        ("alarm", "alarm:otterworks-cw-notifications-dlq-depth", "MISSING"),
        ("dynamodb", "dynamodb:otterworks-cw-notification-preferences", "MISSING"),
    ],
)
check(
    "missing summary counts two resources",
    summary_matches(parsed, drift=0, resources=0, missing=2, unowned=[], checked=["sqs", "sns", "dynamodb", "alarm"]),
)

result, parsed = run_fixture("unowned.json")
check("unowned resources do not fail", result.returncode == 0, f"exit {result.returncode}")
check(
    "unowned fixture identifies the extra table and topic",
    summary_matches(parsed, drift=0, resources=0, missing=0, unowned=["otterworks-cw-scratch", "otterworks-cw-scratch"], checked=["sqs", "sns", "dynamodb", "alarm"])
    and sorted(row["kind"] for row in parsed["rows"] if row["status"] == "UNOWNED") == ["dynamodb", "sns"],
)

result, parsed = run_fixture("legacy-sqs.json")
check("legacy SQS fixture exits 0", result.returncode == 0, f"exit {result.returncode}")
check(
    "legacy fixture checks only SQS and emits no new-kind rows",
    summary_matches(parsed, drift=0, resources=0, missing=0, unowned=[], checked=["sqs"])
    and parsed is not None
    and {row["kind"] for row in parsed["rows"]} == {"sqs"},
)

result, parsed = run_fixture("malformed.json")
check("malformed JSON exits 2", result.returncode == 2, f"exit {result.returncode}: {result.stderr.strip()}")
result, parsed = run_fixture("non-object-section.json")
check("non-object section exits 2", result.returncode == 2, f"exit {result.returncode}: {result.stderr.strip()}")

result, _ = run_fixture("clean.json", json_output=False)
lines = result.stdout.splitlines()
check("table output exits 0", result.returncode == 0, f"exit {result.returncode}")
check(
    "table output includes the resource header and summary",
    len(lines) >= 2
    and lines[0].split() == ["RESOURCE", "ATTRIBUTE", "LIVE", "GIT", "ROOT", "FILE:LINE", "STATUS"]
    and lines[-1] == "drift: 0 attribute(s) on 0 resource(s); missing: 0; unowned: 0 (-); checked: sqs,sns,dynamodb,alarm",
)

print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
PY
