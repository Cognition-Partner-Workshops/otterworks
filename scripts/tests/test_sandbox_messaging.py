"""Offline tests for scripts/lib/sandbox_messaging.py against moto.

The fixture mirrors the repaired modules/messaging analytics path (SNS topic,
analytics_events queue with a maxReceiveCount=5 redrive policy into its DLQ)
plus the sandbox ledger table. Run: python -m pytest scripts/tests/test_sandbox_messaging.py
"""
import importlib.util
import json
import pathlib

import boto3
import pytest
from moto import mock_aws

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sandbox_messaging", ROOT / "scripts/lib/sandbox_messaging.py")
sm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sm)

TOKEN = "rs-20261006-zz"
REGION = "us-east-1"


@pytest.fixture
def sandbox(monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        s = boto3.session.Session(region_name=REGION)
        sqs, sns, ddb = s.client("sqs"), s.client("sns"), s.client("dynamodb")
        topic = sns.create_topic(Name=f"{TOKEN}-events-dev")["TopicArn"]
        dlq_url = sqs.create_queue(QueueName=f"{TOKEN}-analytics-events-dlq-dev",
                                   Attributes={"MessageRetentionPeriod": "1209600"})["QueueUrl"]
        dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        src_url = sqs.create_queue(QueueName=f"{TOKEN}-analytics-events-dev", Attributes={
            "VisibilityTimeout": "120", "MessageRetentionPeriod": "259200",
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": 5})})["QueueUrl"]
        src_arn = sqs.get_queue_attributes(QueueUrl=src_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        sns.subscribe(TopicArn=topic, Protocol="sqs", Endpoint=src_arn)
        ddb.create_table(TableName=f"{TOKEN}-analytics-ledger", BillingMode="PAY_PER_REQUEST",
                         AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
                         KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}])
        outputs = {"run_token": TOKEN, "region": REGION, "events_topic_arn": topic,
                   "analytics_queue_url": src_url, "analytics_queue_arn": src_arn,
                   "analytics_dlq_url": dlq_url, "analytics_dlq_arn": dlq_arn,
                   "ledger_table_name": f"{TOKEN}-analytics-ledger"}
        yield sm.Sandbox(outputs, session=s), s


class MoveTaskEmulator:
    """moto 5.x has no StartMessageMoveTask; emulate its documented DLQ -> original source move."""

    def __init__(self, client, sources, dlq_urls):
        self._c, self._sources, self._dlqs, self._tasks = client, sources, dlq_urls, {}

    def __getattr__(self, name):
        return getattr(self._c, name)

    def start_message_move_task(self, SourceArn, DestinationArn=None):
        assert DestinationArn is None, "the sandbox redrives to the original source queue"
        moved = 0
        while True:
            msgs = self._c.receive_message(QueueUrl=self._dlqs[SourceArn], MaxNumberOfMessages=10,
                                           MessageAttributeNames=["All"]).get("Messages", [])
            if not msgs:
                break
            for m in msgs:
                self._c.send_message(QueueUrl=self._sources[SourceArn], MessageBody=m["Body"])
                self._c.delete_message(QueueUrl=self._dlqs[SourceArn], ReceiptHandle=m["ReceiptHandle"])
                moved += 1
        self._tasks[SourceArn] = {"Status": "COMPLETED", "SourceArn": SourceArn,
                                  "ApproximateNumberOfMessagesMoved": moved}
        return {"TaskHandle": f"task-{moved}"}

    def list_message_move_tasks(self, SourceArn, MaxResults=1):
        return {"Results": [dict(self._tasks[SourceArn])]}


def drain(sb, **kw):
    kw.setdefault("idle_seconds", 1)
    kw.setdefault("max_seconds", 60)
    return sb.consume(wait_seconds=0, **kw)


def test_failed_events_are_captured_and_redriven_exactly_once(sandbox):
    sb, _ = sandbox
    ids = sb.publish(4, batch="t1")

    failed = drain(sb, fault="ledger")
    assert failed["applied"] == 0 and failed["failed"] >= 4
    assert sb.depth(sb.o["analytics_queue_url"]) == 0
    assert sb.depth(sb.o["analytics_dlq_url"]) == 4, "every exhausted event must land in the DLQ"
    assert sb.ledger() == (set(), 0)

    sb.sqs = MoveTaskEmulator(sb.sqs, {sb.o["analytics_dlq_arn"]: sb.o["analytics_queue_url"]},
                              {sb.o["analytics_dlq_arn"]: sb.o["analytics_dlq_url"]})
    task = sb.redrive(timeout=5, poll=0.1)
    assert task["Status"] == "COMPLETED" and task["ApproximateNumberOfMessagesMoved"] == 4
    assert sb.depth(sb.o["analytics_dlq_url"]) == 0

    first = drain(sb, crash_after_write=True)
    assert first["crashed"] == 4 and first["applied"] == 4
    assert first["duplicates"] == 4 and first["deleted"] == 4, "redelivery after the crash must be a no-op write"
    assert drain(sb)["received"] == 0

    result = sb.verify(ids)
    assert result["exactly_once"], result
    assert result["rollup_events"] == 4


def test_duplicate_publish_of_same_event_is_applied_once(sandbox):
    sb, _ = sandbox
    ids = sb.publish(2, batch="dup")
    sb.publish(2, batch="dup")
    stats = drain(sb)
    assert stats["applied"] == 2 and stats["duplicates"] == 2
    assert sb.verify(ids)["exactly_once"]


def test_verify_fails_when_events_are_missing(sandbox):
    sb, _ = sandbox
    ids = sb.publish(3, batch="miss")
    drain(sb, fault="ledger")
    result = sb.verify(ids)
    assert not result["exactly_once"]
    assert result["missing"] == sorted(ids)
    assert result["analytics_dlq_depth"] == 3


def test_reset_purges_queues_and_ledger(sandbox):
    sb, _ = sandbox
    sb.publish(2, batch="r")
    drain(sb)
    sb.publish(1, batch="r2")
    out = sb.reset()
    assert out["ledger_items_deleted"] == 3  # two events + rollup
    assert sb.ledger() == (set(), 0)
    assert sb.depth(sb.o["analytics_queue_url"]) == 0


def test_guard_refuses_foreign_resources(sandbox):
    sb, _ = sandbox
    with pytest.raises(sm.SandboxError):
        sb.guard("https://sqs.us-east-1.amazonaws.com/111111111111/otterworks-analytics-events-dev")
    bad = dict(sb.o, ledger_table_name="otterworks-dev-analytics")
    with pytest.raises(sm.SandboxError):
        sm.Sandbox(bad, session=sandbox[1])


def test_cli_round_trip(sandbox, tmp_path, monkeypatch, capsys):
    sb, s = sandbox
    out = tmp_path / "outputs.json"
    out.write_text(json.dumps({k: {"value": v} for k, v in sb.o.items()}))
    ids = tmp_path / "ids.json"
    monkeypatch.setattr(sm.boto3.session, "Session", lambda region_name=None: s)
    assert sm.main(["--outputs", str(out), "publish", "--count", "2", "--batch", "cli", "--ids-file", str(ids)]) == 0
    assert sm.main(["--outputs", str(out), "consume", "--idle-seconds", "1"]) == 0
    assert sm.main(["--outputs", str(out), "verify", "--ids-file", str(ids)]) == 0
    assert json.loads(ids.read_text()) == ["cli-0000", "cli-0001"]
    assert sm.main(["--outputs", str(out), "status"]) == 0
    capsys.readouterr()


def _rc(address, actions, after, mode="managed"):
    return {"address": address, "mode": mode, "change": {"actions": actions, "after": after}}


def test_plan_guard_accepts_token_scoped_creates():
    plan = {"resource_changes": [
        _rc("module.messaging.aws_sqs_queue.analytics_events", ["create"],
            {"name": f"{TOKEN}-analytics-events-dev", "tags_all": {"run_token": TOKEN}}),
        _rc("module.messaging.aws_cloudwatch_metric_alarm.dlq_depth[\"analytics_events\"]", ["create"],
            {"alarm_name": f"{TOKEN}-analytics-events-dlq-dev-depth", "tags_all": {"run_token": TOKEN}}),
        _rc("aws_sqs_queue_redrive_allow_policy.dlq", ["create"], {"queue_url": None}),
    ]}
    assert sm.plan_guard(plan, TOKEN) == []


@pytest.mark.parametrize("change,needle", [
    (_rc("aws_sqs_queue.x", ["delete"], None), "is not create/update"),
    (_rc("aws_sqs_queue.x", ["delete", "create"], {"name": f"{TOKEN}-x"}), "is not create/update"),
    (_rc("aws_sqs_queue.x", ["create"], {"name": "otterworks-analytics-events-dev"}), "does not start with"),
    (_rc("aws_sqs_queue.x", ["create"], {"name": f"{TOKEN}-x", "tags_all": {"run_token": "lp-20261006-ab"}}), "run_token tag"),
    ({"address": "aws_sqs_queue.x", "change": {"actions": ["no-op"], "importing": {"id": "q"}, "after": {}}}, "imports"),
])
def test_plan_guard_rejects_anything_outside_the_token(change, needle):
    problems = sm.plan_guard({"resource_changes": [change]}, TOKEN)
    assert any(needle in p for p in problems), problems


def test_plan_guard_allows_delete_only_when_asked():
    plan = {"resource_changes": [_rc("aws_sqs_queue.x", ["delete"], None)]}
    assert sm.plan_guard(plan, TOKEN, allow_delete=True) == []
    assert sm.plan_guard({"resource_drift": [{}], "resource_changes": []}, TOKEN)


def test_plan_guard_cli(tmp_path):
    f = tmp_path / "plan.json"
    f.write_text(json.dumps({"resource_changes": [_rc("aws_sqs_queue.x", ["create"], {"name": "foreign"})]}))
    assert sm.main(["plan-guard", "--plan-json", str(f), "--run-token", TOKEN]) == 1
