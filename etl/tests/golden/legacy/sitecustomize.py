"""Golden-harness shim for the legacy ETL scripts.

``etl/run.sh`` exports ``PYTHONPATH=/opt/etl``; the harness mounts this file at
``/opt/etl/sitecustomize.py`` so the interpreter imports it before the script.
The scripts themselves are never modified. Everything is driven by env vars and
is a no-op when they are unset:

GOLDEN_AWS_ENDPOINT_URL
    Injected as ``endpoint_url`` into every boto3 client/resource that does not
    set one (boto3 1.26 predates ``AWS_ENDPOINT_URL``). SQS ``QueueUrl``
    parameters that point at real AWS
    (``https://sqs.<region>.amazonaws.com/<account>/<name>``) are rewritten to
    ``<endpoint>/000000000000/<name>``.
GOLDEN_FROZEN_TIME
    ISO-8601 instant; wall-clock time (``datetime.now``, ``time.time``, gzip
    mtimes) is frozen there with freezegun. ``time.monotonic`` and
    ``time.perf_counter`` stay real so polling deadlines still expire.
    pandas is imported before the clock is frozen: pandas 1.3's C extensions
    subclass ``datetime`` and refuse to load against freezegun's FakeDatetime.

If the shim cannot be installed the process exits with code 97 instead of
letting a script run against an unpatched SDK.
"""

import os
import re
import sys

SHIM_FAILURE_EXIT_CODE = 97
LOCALSTACK_ACCOUNT_ID = "000000000000"
_AWS_SQS_URL = re.compile(
    r"^https://sqs\.[a-z0-9-]+\.amazonaws\.com/\d{12}/(?P<name>[A-Za-z0-9_-]+(?:\.fifo)?)$"
)


def rewrite_queue_url(url, endpoint):
    match = _AWS_SQS_URL.match(url or "")
    if not match:
        return url
    return "%s/%s/%s" % (
        endpoint.rstrip("/"),
        LOCALSTACK_ACCOUNT_ID,
        match.group("name"),
    )


def install_aws_endpoint(endpoint):
    import boto3.session

    original_client = boto3.session.Session.client
    if getattr(original_client, "_golden_shim", False):
        return

    def rewrite_sqs_params(params, **_kwargs):
        if "QueueUrl" in params:
            params["QueueUrl"] = rewrite_queue_url(params["QueueUrl"], endpoint)

    def client(self, service_name, *args, **kwargs):
        if not kwargs.get("endpoint_url"):
            kwargs["endpoint_url"] = endpoint
        created = original_client(self, service_name, *args, **kwargs)
        if service_name == "sqs":
            created.meta.events.register(
                "before-parameter-build.sqs", rewrite_sqs_params
            )
        return created

    client._golden_shim = True
    # Session.resource builds its client through Session.client, so resources
    # are covered too.
    boto3.session.Session.client = client


# Imported before freezing; see module docstring.
PRE_FREEZE_IMPORTS = ("pandas",)


def install_frozen_clock(frozen_time):
    import importlib
    import time

    for name in PRE_FREEZE_IMPORTS:
        try:
            importlib.import_module(name)
        except ImportError:
            pass

    from freezegun import freeze_time

    real_monotonic, real_perf_counter = time.monotonic, time.perf_counter
    freezer = freeze_time(frozen_time, tz_offset=0)
    freezer.start()
    time.monotonic, time.perf_counter = real_monotonic, real_perf_counter
    return freezer


def _install():
    endpoint = os.environ.get("GOLDEN_AWS_ENDPOINT_URL")
    frozen_time = os.environ.get("GOLDEN_FROZEN_TIME")
    if not endpoint and not frozen_time:
        return
    try:
        if endpoint:
            install_aws_endpoint(endpoint)
        if frozen_time:
            install_frozen_clock(frozen_time)
    except Exception as exc:  # noqa: BLE001 - any failure must stop the run
        sys.stderr.write("[golden-shim] failed to install: %r\n" % (exc,))
        sys.stderr.flush()
        os._exit(SHIM_FAILURE_EXIT_CODE)
    sys.stderr.write(
        "[golden-shim] endpoint=%s frozen_time=%s\n"
        % (endpoint or "-", frozen_time or "-")
    )


_install()
