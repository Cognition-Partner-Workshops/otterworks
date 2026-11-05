"""observability/prometheus/kyc_upload_slo.yml checked and unit-tested with promtool.

The rule file records the KYC upload p99 and pages on it; the cases in
observability/prometheus/tests/kyc_upload_slo_test.yml show the page firing
above 2 s, the warning firing above 1.5 s and both staying quiet below.

    uv run --with httpx==0.27.2 --with pyyaml==6.0.2 --with PyJWT==2.9.0 \\
        --with redis==5.2.1 --with pytest==8.3.5 pytest incident/tests

promtool comes from PATH, else from the PROMTOOL_IMAGE container.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from test_error_ratio import promtool_cmd

PROM_DIR = Path(__file__).resolve().parents[2] / "observability" / "prometheus"
RULES = PROM_DIR / "kyc_upload_slo.yml"
TESTS = PROM_DIR / "tests" / "kyc_upload_slo_test.yml"


def run_promtool(*args: str) -> None:
    out = subprocess.run(
        [*promtool_cmd(PROM_DIR), *args],
        cwd=PROM_DIR,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr


def test_rule_file_is_valid() -> None:
    run_promtool("check", "rules", RULES.name)


def test_rule_file_is_loaded_by_prometheus() -> None:
    config = yaml.safe_load((PROM_DIR / "prometheus.yml").read_text())
    assert RULES.name in config["rule_files"]


def test_alerts_carry_a_runbook_and_page_the_platform_rotation() -> None:
    rules = [r for g in yaml.safe_load(RULES.read_text())["groups"] for r in g["rules"]]
    assert "job:kyc_upload_duration_seconds:p99" in {r.get("record") for r in rules}
    alerts = {r["alert"]: r for r in rules if "alert" in r}
    assert alerts["KycUploadLatencyP99High"]["for"] == "10m"
    assert alerts["KycUploadLatencyP99High"]["labels"]["severity"] == "critical"
    assert alerts["KycUploadLatencyP99Elevated"]["for"] == "15m"
    assert alerts["KycUploadLatencyP99Elevated"]["labels"]["severity"] == "warning"
    for rule in alerts.values():
        assert rule["labels"]["team"] == "platform"
        assert rule["annotations"]["runbook_url"].endswith("docs/runbooks/kyc-upload-latency.md")


def test_page_fires_above_the_objective_and_stays_quiet_below() -> None:
    run_promtool("test", "rules", str(TESTS.relative_to(PROM_DIR)))
