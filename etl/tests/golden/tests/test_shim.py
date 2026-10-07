import importlib.util
import json
import os
import subprocess
import sys

import boto3
import pytest
from botocore.awsrequest import AWSResponse
from urllib.parse import urlsplit

from harness import settings

SHIM = settings.LEGACY_DIR / "sitecustomize.py"
REAL_SQS_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/otterworks-analytics"


def load_shim(monkeypatch):
    monkeypatch.delenv("GOLDEN_AWS_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("GOLDEN_FROZEN_TIME", raising=False)
    spec = importlib.util.spec_from_file_location("golden_sitecustomize", SHIM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_noop_without_env(monkeypatch):
    original = boto3.session.Session.client
    load_shim(monkeypatch)
    assert boto3.session.Session.client is original


@pytest.mark.parametrize(
    "url,expected",
    [
        (REAL_SQS_URL, "http://localhost:4566/000000000000/otterworks-analytics"),
        (
            "https://sqs.eu-west-1.amazonaws.com/999999999999/q.fifo",
            "http://localhost:4566/000000000000/q.fifo",
        ),
        (
            "http://localhost:4566/000000000000/otterworks-analytics",
            "http://localhost:4566/000000000000/otterworks-analytics",
        ),
        ("https://example.com/123456789012/q", "https://example.com/123456789012/q"),
    ],
)
def test_rewrite_queue_url(monkeypatch, url, expected):
    assert (
        load_shim(monkeypatch).rewrite_queue_url(url, "http://localhost:4566/")
        == expected
    )


class _Raw:
    def stream(self, **_kwargs):
        yield b"{}"


def test_endpoint_injection_and_sqs_rewrite(monkeypatch):
    monkeypatch.setattr(boto3.session.Session, "client", boto3.session.Session.client)
    load_shim(monkeypatch).install_aws_endpoint("http://localstack.test:4566")
    session = boto3.session.Session(
        aws_access_key_id="a", aws_secret_access_key="b", region_name="us-east-1"
    )

    assert session.client("s3").meta.endpoint_url == "http://localstack.test:4566"
    assert (
        session.client("s3", endpoint_url="http://explicit:1").meta.endpoint_url
        == "http://explicit:1"
    )
    assert (
        session.resource("dynamodb").meta.client.meta.endpoint_url
        == "http://localstack.test:4566"
    )

    sent = []
    sqs = session.client("sqs")

    def capture(request, **_kwargs):
        sent.append(request)
        return AWSResponse(request.url, 200, {}, _Raw())

    sqs.meta.events.register("before-send", capture)
    sqs.get_queue_attributes(QueueUrl=REAL_SQS_URL, AttributeNames=["All"])
    assert urlsplit(sent[0].url).netloc == "localstack.test:4566"
    assert (
        json.loads(sent[0].body)["QueueUrl"]
        == "http://localstack.test:4566/000000000000/otterworks-analytics"
    )


def run_python(code, **env):
    full_env = {k: v for k, v in os.environ.items() if not k.startswith("GOLDEN_")}
    full_env.update(env, PYTHONPATH=str(settings.LEGACY_DIR))
    return subprocess.run(
        [sys.executable, "-c", code], env=full_env, capture_output=True, text=True
    )


def test_frozen_clock_but_real_monotonic():
    code = (
        "import gzip, time\n"
        "from datetime import datetime, timezone\n"
        "m = time.monotonic(); time.sleep(0.05)\n"
        "print(datetime.now(tz=timezone.utc).isoformat(), datetime.now().isoformat(), time.time(),"
        " gzip.compress(b'x')[4:8].hex(), time.monotonic() > m)\n"
    )
    proc = run_python(code, GOLDEN_FROZEN_TIME="2026-03-15T02:00:00Z")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == [
        "2026-03-15T02:00:00+00:00",
        "2026-03-15T02:00:00",
        "1773540000.0",
        "a012b669",
        "True",
    ]
    assert "[golden-shim] endpoint=- frozen_time=2026-03-15T02:00:00Z" in proc.stderr


def test_install_failure_aborts_the_run():
    proc = run_python("print('script ran')", GOLDEN_FROZEN_TIME="not a timestamp")
    assert proc.returncode == 97
    assert "script ran" not in proc.stdout
    assert "[golden-shim] failed to install" in proc.stderr
