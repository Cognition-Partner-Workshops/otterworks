import csv
import hashlib
import hmac
import json
from collections import Counter
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import sqlite3
import sys
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from demos.finops.signals.forwarder import forward, lambda_handler, webhook_sender
from demos.finops.signals.replay import sqlite_claims
from demos.finops.workload.compare import measure

FIXTURES = Path(__file__).resolve().parents[2] / "demos" / "finops" / "fixtures"


def test_finops_billing_has_matched_daily_windows_and_unallocated_charge():
    with (FIXTURES / "billing.csv").open(newline="") as export:
        rows = list(csv.DictReader(export))
    tagged = [row for row in rows if row["service"]]
    assert {row["window"] for row in tagged} == {"baseline", "observed"}
    assert len({row["service"] for row in tagged}) == 2
    assert set(Counter((row["service"], row["window"]) for row in tagged).values()) == {7}
    assert all(row["run_tag"] == "FINOPS_20261128" and row["environment"] == "dev" for row in rows)
    assert all(Decimal(row["usage_quantity"]) * Decimal(row["unit_rate_usd"]) == Decimal(row["cost_usd"]) for row in rows)
    unallocated = [row for row in rows if not row["service"]]
    assert len(unallocated) == 1
    assert unallocated[0]["resource_id"] == ""


def test_cost_anomaly_replay_signs_payload_and_suppresses_duplicate_across_connections(tmp_path):
    state = tmp_path / "ledger.sqlite"
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.status = 202
    key = b"test-replay-key"

    with patch("demos.finops.signals.forwarder.build_opener", return_value=opener):
        send = webhook_sender("https://example.invalid/automation", "test-secret", key)

    def replay(fixture):
        event = json.loads((FIXTURES / fixture).read_text())
        with closing(sqlite3.connect(state)) as ledger:
            claim, release = sqlite_claims(ledger)
            receipt, = forward(
                event, claim, send, release=release,
                run_tag="FINOPS_20261128", environment="dev", source="signed-sns-replay",
            )
        return receipt

    first = replay("anomaly-sns.json")
    second = replay("anomaly-sns-duplicate.json")
    assert first["result"] == "accepted"
    assert second["result"] == "duplicate_suppressed"
    assert first["dedupe_key"] == second["dedupe_key"]
    assert first["sns_message_id"] != second["sns_message_id"]
    opener.open.assert_called_once()
    request = opener.open.call_args.args[0]
    digest = hmac.new(key, request.data, hashlib.sha256).hexdigest()
    assert request.get_header("X-finops-replay-signature") == f"sha256={digest}"
    assert json.loads(request.data)["notification_id"] == first["notification_id"]


@pytest.mark.parametrize(
    ("failure", "status", "replayed_result", "posts"),
    [
        (HTTPError("https://example.invalid", 401, "Unauthorized", {}, None), 401, "accepted", 2),
        (HTTPError("https://example.invalid", 500, "Server error", {}, None), 500, "duplicate_suppressed", 1),
        (URLError("Connection error"), None, "duplicate_suppressed", 1),
    ],
)
def test_cost_anomaly_replay_releases_only_unauthorized_claim(tmp_path, failure, status, replayed_result, posts):
    state = tmp_path / "ledger.sqlite"
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.status = 202
    opener.open.side_effect = [failure, opener.open.return_value]

    def replay(fixture, secret):
        event = json.loads((FIXTURES / fixture).read_text())
        with patch("demos.finops.signals.forwarder.build_opener", return_value=opener):
            send = webhook_sender("https://example.invalid/automation", secret, b"test-replay-key")
        with closing(sqlite3.connect(state)) as ledger:
            claim, release = sqlite_claims(ledger)
            receipt, = forward(
                event, claim, send, release=release,
                run_tag="FINOPS_20261128", environment="dev", source="signed-sns-replay",
            )
        return receipt

    first = replay("anomaly-sns.json", "stale-test-secret")
    second = replay("anomaly-sns-duplicate.json", "corrected-test-secret")
    assert first["result"] == "delivery_unconfirmed"
    assert first["webhook_status"] == status
    assert second["result"] == replayed_result
    assert opener.open.call_count == posts


def test_lambda_releases_unauthorized_claim_before_raising(monkeypatch):
    monkeypatch.setenv("FINOPS_DEDUPE_TABLE", "test-ledger")
    monkeypatch.setenv("DEVIN_WEBHOOK_URL", "https://example.invalid/automation")
    monkeypatch.setenv("DEVIN_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("FINOPS_RUN_TAG", "FINOPS_20261128")
    monkeypatch.setenv("FINOPS_ENVIRONMENT", "dev")
    boto3 = MagicMock()
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    table = boto3.resource.return_value.Table.return_value
    opener = MagicMock()
    opener.open.side_effect = HTTPError("https://example.invalid", 401, "Unauthorized", {}, None)
    event = json.loads((FIXTURES / "anomaly-sns.json").read_text())
    key = "aws.cost-anomaly:" + json.loads(event["Records"][0]["Sns"]["Message"])["anomalyId"]

    with patch("demos.finops.signals.forwarder.build_opener", return_value=opener):
        with pytest.raises(RuntimeError, match="Webhook delivery unconfirmed"):
            lambda_handler(event, None)

    table.put_item.assert_called_once_with(
        Item={"dedupe_key": key}, ConditionExpression="attribute_not_exists(dedupe_key)",
    )
    table.delete_item.assert_called_once_with(Key={"dedupe_key": key})


def test_dev_settings_gate_checks_capacity_and_audit_on_the_same_workload():
    settings = {"root_volume_gib": 36, "app_retention_days": 7, "audit_retention_days": 90}
    healthy = measure(settings)
    unhealthy = measure({**settings, "root_volume_gib": 28})
    audit_breach = measure({**settings, "audit_retention_days": 60})
    assert all(run["requests"] == 100 for run in (healthy, unhealthy, audit_breach))
    assert len({run["workload_sha256"] for run in (healthy, unhealthy, audit_breach)}) == 1
    assert healthy["health"] == "pass"
    assert unhealthy["health"] == "fail"
    assert unhealthy["errors"] == unhealthy["disk_pressure_responses"] > 0
    assert audit_breach["health"] == "fail"
    assert audit_breach["gates"]["audit_policy_unchanged"] is False
