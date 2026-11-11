import json
from types import SimpleNamespace

import pytest

from integration.wave0.wait_ready import wait_ready


def runner(running=True, logs=""):
    def run(args, **kwargs):
        if args[1] == "inspect":
            return SimpleNamespace(stdout=json.dumps({"Running": running, "StartedAt": "now"}))
        assert args[1:4] == ["logs", "--since", "now"]
        return SimpleNamespace(stdout=logs, stderr="")
    return run


def test_ready():
    wait_ready("ci", ["fees-billing"], run=runner(logs="Started FeesBillingApplication in 4s"))


def test_empty():
    wait_ready("ci", [], run=lambda *args, **kwargs: pytest.fail("no containers expected"))


def test_exit():
    with pytest.raises(RuntimeError, match="exited"):
        wait_ready("ci", ["fees-billing"], run=runner(running=False))


def test_timeout():
    with pytest.raises(TimeoutError, match="not ready"):
        wait_ready("ci", ["fees-billing"], timeout=0, run=runner())
