"""METRIC_EXPRS["error_ratio"] evaluated by real PromQL (promtool test rules).

A fresh service exports no 5xx series, so errors count as zero only while the
total request rate is positive; no total series, no traffic or a NaN total
must stay empty so the after gate fails instead of passing on no evidence.

    uv run --with httpx==0.27.2 --with pyyaml==6.0.2 --with PyJWT==2.9.0 \\
        --with redis==5.2.1 --with pytest==8.3.5 pytest incident/tests

promtool comes from PATH, else from the PROMTOOL_IMAGE container.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("incident_harness", HERE.parent / "incident.py")
assert SPEC and SPEC.loader
incident = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(incident)

EXPR = incident.METRIC_EXPRS["error_ratio"]
PROMTOOL_IMAGE = os.environ.get("PROMTOOL_IMAGE", "mirror.gcr.io/prom/prometheus:v2.51.0")

OK = 'http_requests_total{job="document-service",handler="/api/v1/documents/",status="200"}'
ERR = 'http_requests_total{job="document-service",handler="/api/v1/documents/",status="503"}'

# Counters scraped every 15s for 5m; +15 per step is 1 rps.
CASES = {
    "traffic, no 5xx series -> 0": ([(OK, "0+15x20")], 0.0),
    "traffic with 5xx -> their share": ([(OK, "0+12x20"), (ERR, "0+3x20")], 0.2),
    "5xx series present but zero -> 0": ([(OK, "0+15x20"), (ERR, "4+0x20")], 0.0),
    "no http_requests_total series -> empty": (
        [('otterworks_request_log_bytes{job="document-service"}', "1x20")],
        None,
    ),
    "series for another job only -> empty": (
        [('http_requests_total{job="api-gateway",status="200"}', "0+15x20")],
        None,
    ),
    "no traffic (flat counter) -> empty": ([(OK, "7+0x20")], None),
    "no traffic, flat 5xx series -> empty": ([(OK, "7+0x20"), (ERR, "2+0x20")], None),
    "NaN total -> empty": ([(OK, "NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN")], None),
}


def promtool_cmd(workdir: Path) -> list[str]:
    if shutil.which("promtool"):
        return ["promtool"]
    if shutil.which("docker"):
        return [
            "docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{workdir}:/w", "-w", "/w",
            "--entrypoint", "promtool", PROMTOOL_IMAGE,
        ]  # fmt: skip
    pytest.skip("needs promtool or docker for real PromQL evaluation")


def run_promql(tmp_path: Path, series: list[tuple[str, str]], expected: float | None) -> None:
    samples = [] if expected is None else [{"labels": "{}", "value": expected}]
    doc = {
        "rule_files": [],
        "evaluation_interval": "15s",
        "tests": [
            {
                "interval": "15s",
                "input_series": [{"series": s, "values": v} for s, v in series],
                "promql_expr_test": [{"expr": EXPR, "eval_time": "3m", "exp_samples": samples}],
            }
        ],
    }
    (tmp_path / "t.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    out = subprocess.run(
        [*promtool_cmd(tmp_path), "test", "rules", "t.yml"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr


@pytest.mark.parametrize(("series", "expected"), CASES.values(), ids=CASES.keys())
def test_error_ratio_promql(
    tmp_path: Path, series: list[tuple[str, str]], expected: float | None
) -> None:
    run_promql(tmp_path, series, expected)


def test_empty_result_fails_the_gate_and_zero_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(incident, "prom_query", lambda _cat, _expr: [])
    missing = incident.prom_scalar({}, EXPR)
    assert missing is None

    findings: list[str] = []
    incident._threshold_checks(findings, {"error_ratio": missing}, {"error_ratio_max": 0.01})
    assert findings and incident.NO_SAMPLES in findings[0]

    findings = []
    incident._threshold_checks(findings, {"error_ratio": 0.0}, {"error_ratio_max": 0.01})
    assert findings == []

    incident._threshold_checks(findings, {"error_ratio": 0.2}, {"error_ratio_max": 0.01})
    assert len(findings) == 1
