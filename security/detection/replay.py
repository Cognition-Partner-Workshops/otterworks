# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "pyyaml"]
# ///
"""Replay DAST classes and prove quiet -> firing -> delivered without fixing them."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "attack-classes.yaml"
POLL_SECONDS = 3
ALERTMANAGER_SETTLE_SECONDS = 60


class SetupError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(UTC).isoformat()


def load_classes(path: Path = MANIFEST) -> dict:
    classes = yaml.safe_load(path.read_text())["classes"]
    for name, spec in classes.items():
        for field in ("findings", "alerts", "counters"):
            if not spec.get(field) or len(set(spec[field])) != len(spec[field]):
                raise SetupError(f"{name}: invalid {field}")
        for field in (
            "quiet_budget_seconds",
            "time_budget_seconds",
            "probe_budget_seconds",
        ):
            if not isinstance(spec.get(field), int) or spec[field] <= 0:
                raise SetupError(f"{name}: invalid {field}")
    return classes


def service_urls() -> dict[str, str]:
    urls = {
        name: os.getenv(f"DETECT_{name.upper()}_URL", default).rstrip("/")
        for name, default in {
            "gateway": "http://localhost:8080",
            "prometheus": "http://localhost:9090",
            "alertmanager": "http://localhost:9093",
            "sink": "http://localhost:9095",
        }.items()
    }
    for name, url in urls.items():
        parsed = urlsplit(url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.username
        ):
            raise SetupError(
                f"Invalid {name} URL (embedded credentials are not supported)"
            )
    return urls


def get_json(client, url: str, **kwargs):
    response = client.get(url, **kwargs)
    response.raise_for_status()
    return response.json()


def prometheus_data(client, base: str, path: str, **kwargs):
    payload = get_json(client, base + path, **kwargs)
    if payload.get("status") != "success":
        raise SetupError(f"Prometheus rejected {path}")
    return payload["data"]


def alert_states(groups: list[dict], expected: list[str]) -> dict:
    found = {}
    for group in groups:
        for rule in group.get("rules", []):
            name = rule.get("name")
            if name not in expected or rule.get("type") != "alerting":
                continue
            if rule.get("health") != "ok":
                raise SetupError(
                    f"Rule {name} is unhealthy: {rule.get('lastError', '')}"
                )
            if name in found:
                raise SetupError(f"Duplicate rule {name}; use a dedicated Prometheus")
            found[name] = {
                "state": rule["state"],
                "instances": [
                    {
                        key: alert.get(key)
                        for key in ("labels", "state", "activeAt", "value")
                    }
                    for alert in rule.get("alerts", [])
                ],
            }
    missing = set(expected) - found.keys()
    if missing:
        raise SetupError(f"Missing detection rules: {', '.join(sorted(missing))}")
    return {name: found[name] for name in expected}


def read_alerts(client, urls: dict, spec: dict) -> dict:
    data = prometheus_data(
        client, urls["prometheus"], "/api/v1/rules", params={"type": "alert"}
    )
    return alert_states(data["groups"], spec["alerts"])


def is_quiet(states: dict) -> bool:
    return bool(states) and all(
        state["state"] == "inactive" for state in states.values()
    )


def active_class_alerts(client, urls: dict, spec: dict) -> list[dict]:
    alerts = get_json(client, urls["alertmanager"] + "/api/v2/alerts")
    if not isinstance(alerts, list):
        raise SetupError("Alertmanager did not return an alert list")
    return [
        alert
        for alert in alerts
        if alert.get("labels", {}).get("alertname") in spec["alerts"]
    ]


def all_firing(states: dict) -> bool:
    return bool(states) and all(state["state"] == "firing" for state in states.values())


def snapshot(client, urls: dict, spec: dict) -> dict:
    counters = {}
    for selector in spec["counters"]:
        data = prometheus_data(
            client, urls["prometheus"], "/api/v1/query", params={"query": selector}
        )
        if data["resultType"] != "vector" or not data["result"]:
            raise SetupError(f"No scraped series for {selector}")
        counters[selector] = data["result"]
    return {"at": now(), "counters": counters}


def sink_records(client, urls: dict) -> list[dict]:
    records = get_json(client, urls["sink"] + "/security")
    if not isinstance(records, list):
        raise SetupError("Sink /security did not return a delivery history")
    return records


def delivered_alerts(
    records: list[dict], class_name: str, attack_started: str
) -> set[str]:
    names = set()
    started = datetime.fromisoformat(attack_started)
    for record in records:
        received = datetime.fromisoformat(record["received_at"].replace("Z", "+00:00"))
        if received < started:
            continue
        for alert in record.get("payload", {}).get("alerts", []):
            labels = alert.get("labels", {})
            if (
                alert.get("status") == "firing"
                and labels.get("attack_class") == class_name
            ):
                names.add(labels.get("alertname", ""))
    return names


def probe_command(class_spec: dict, gateway: str, report_dir: Path) -> list[str]:
    command = [
        "uv",
        "run",
        str(ROOT / "security/dast/harness/dast_scan.py"),
        "--target",
        gateway,
        "--no-baseline",
        "--report-dir",
        str(report_dir),
    ]
    for finding in class_spec["findings"]:
        command.extend(["--only", finding])
    return command


def probe_verdicts(report: dict, expected: list[str]) -> list[dict]:
    results = report.get("results", [])
    if {row["finding_id"] for row in results} != set(expected):
        raise SetupError("DAST report does not contain exactly the requested probes")
    return [
        {key: row[key] for key in ("finding_id", "verdict", "detail")}
        for row in results
    ]


def markdown(report: dict) -> str:
    lines = [
        f"# Detection replay: {report['attack_class']}",
        "",
        f"- Started: {report['started_at']}",
        f"- Exit: {report['exit_code']}",
        f"- Error: {report.get('error') or 'none'}",
        "- seconds_to_fire is the first observed firing time, measured from attack start.",
        "",
        "## Alerts",
        "",
        "| Alert | Before | After | Seconds to fire | activeAt |",
        "|---|---|---|---|---|",
    ]
    for name in report["expected_alerts"]:
        before = report.get("before_alerts", {}).get(name, {}).get("state", "unknown")
        after = report.get("after_alerts", {}).get(name, {}).get("state", "unknown")
        fired = report.get("firing", {}).get(name, {})
        lines.append(
            f"| {name} | {before} | {after} | {fired.get('seconds_to_fire', 'n/a')} | {fired.get('activeAt', 'n/a')} |"
        )
    lines.extend(["", "## Probe verdicts", ""])
    for row in report.get("probe_verdicts", []):
        lines.append(f"- {row['finding_id']}: **{row['verdict']}** — {row['detail']}")
    for title, key in (
        ("Before counters", "before_counters"),
        ("After counters", "after_counters"),
        ("Before alert states", "before_alerts"),
        ("Before Alertmanager alerts", "before_alertmanager_alerts"),
        ("After alert states", "after_alerts"),
        ("Captured security sink payloads", "sink_payloads"),
    ):
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "```json",
                json.dumps(report.get(key), indent=2),
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def write_report(report: dict, base: Path) -> None:
    base.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    base.with_suffix(".md").write_text(markdown(report))
    for name, firing in report.get("firing", {}).items():
        print(
            f"  {name}: firing in {firing['seconds_to_fire']:.1f}s; activeAt={firing['activeAt']}",
            flush=True,
        )
    for row in report.get("probe_verdicts", []):
        print(f"  {row['finding_id']}: {row['verdict']}", flush=True)
    print(f"Reports: {base}.{{json,md}}", flush=True)
    print(
        f"Detection replay {report['attack_class']}: exit {report['exit_code']}"
        + (f" — {report['error']}" if report.get("error") else ""),
        flush=True,
    )


def replay(class_name: str, spec: dict, urls: dict, report_dir: Path) -> int:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    report_dir.mkdir(parents=True, exist_ok=True)
    base = report_dir / f"{class_name}-{stamp}"
    report = {
        "attack_class": class_name,
        "started_at": now(),
        "urls": urls,
        "expected_alerts": spec["alerts"],
        "budgets": {
            key: value for key, value in spec.items() if key.endswith("_seconds")
        },
        "firing": {},
        "probe_verdicts": [],
        "sink_payloads": [],
        "quiet_settle_seconds": ALERTMANAGER_SETTLE_SECONDS,
        "exit_code": 2,
    }
    try:
        with httpx.Client(timeout=10) as client:
            for service, path in (
                ("gateway", "/health"),
                ("alertmanager", "/-/ready"),
                ("sink", "/health"),
            ):
                client.get(urls[service] + path).raise_for_status()
            print(f"BEFORE {class_name}: waiting for inactive rules", flush=True)
            deadline = time.monotonic() + spec["quiet_budget_seconds"]
            quiet_since = None
            while True:
                report["before_alerts"] = read_alerts(client, urls, spec)
                report["before_alertmanager_alerts"] = active_class_alerts(
                    client, urls, spec
                )
                if (
                    is_quiet(report["before_alerts"])
                    and not report["before_alertmanager_alerts"]
                ):
                    if quiet_since is None:
                        quiet_since = time.monotonic()
                    if time.monotonic() - quiet_since >= ALERTMANAGER_SETTLE_SECONDS:
                        break
                else:
                    quiet_since = None
                if time.monotonic() >= deadline:
                    raise SetupError(
                        "Prometheus/Alertmanager did not stay quiet within budget"
                    )
                time.sleep(POLL_SECONDS)
            report["before_counters"] = snapshot(client, urls, spec)
            baseline_deliveries = len(sink_records(client, urls))
            probe_dir = report_dir / f"{class_name}-{stamp}-probes"
            attack_clock = time.monotonic()
            report["attack_started_at"] = now()
            print(f"ATTACK {class_name}: {', '.join(spec['findings'])}", flush=True)
            process = subprocess.run(
                probe_command(spec, urls["gateway"], probe_dir),
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=spec["probe_budget_seconds"],
            )
            probe_dir.mkdir(parents=True, exist_ok=True)
            (probe_dir / "console.log").write_text(process.stdout + process.stderr)
            report["probe_exit_code"] = process.returncode
            if process.returncode not in (0, 1, 3):
                raise SetupError(
                    f"DAST setup failed (exit {process.returncode}); see {probe_dir}/console.log"
                )
            report["probe_verdicts"] = probe_verdicts(
                json.loads((probe_dir / "dast-report.json").read_text()),
                spec["findings"],
            )
            report["probe_finished_at"] = now()
            print(
                f"AFTER {class_name}: waiting for all rules and fresh security delivery",
                flush=True,
            )
            deadline = attack_clock + spec["time_budget_seconds"]
            while True:
                states = read_alerts(client, urls, spec)
                report["after_alerts"] = states
                for name, state in states.items():
                    if state["state"] == "firing" and name not in report["firing"]:
                        report["firing"][name] = {
                            "activeAt": [a["activeAt"] for a in state["instances"]],
                            "observed_at": now(),
                            "seconds_to_fire": round(
                                time.monotonic() - attack_clock, 3
                            ),
                        }
                records = sink_records(client, urls)
                if len(records) < baseline_deliveries:
                    raise SetupError("Sink history was cleared during replay")
                fresh = records[baseline_deliveries:]
                report["sink_payloads"] = [
                    row
                    for row in fresh
                    if delivered_alerts([row], class_name, report["attack_started_at"])
                ]
                delivered = delivered_alerts(
                    fresh, class_name, report["attack_started_at"]
                )
                report["delivered_alerts"] = sorted(delivered)
                if all_firing(states) and set(spec["alerts"]) <= delivered:
                    report["exit_code"] = 0
                    break
                if time.monotonic() >= deadline:
                    report["exit_code"] = 1
                    report["error"] = (
                        "Not all expected alerts were simultaneously firing and delivered within budget"
                    )
                    break
                time.sleep(POLL_SECONDS)
            report["after_counters"] = snapshot(client, urls, spec)
    except (
        SetupError,
        httpx.HTTPError,
        OSError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as exc:
        report["exit_code"] = 2
        report["error"] = str(exc)
    report["finished_at"] = now()
    write_report(report, base)
    return report["exit_code"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "status", "replay"))
    parser.add_argument("attack_class", nargs="?")
    parser.add_argument("--report-dir", type=Path, default=HERE / "reports")
    args = parser.parse_args(argv)
    try:
        classes = load_classes()
        if args.command == "list":
            for name, spec in classes.items():
                print(
                    f"{name}: {', '.join(spec['findings'])} -> {', '.join(spec['alerts'])} ({spec['time_budget_seconds']}s)"
                )
            return 0
        urls = service_urls()
        if args.command == "status":
            with httpx.Client(timeout=10) as client:
                for name, spec in classes.items():
                    print(name)
                    for alert, state in read_alerts(client, urls, spec).items():
                        print(f"  {alert}: {state['state']}")
            return 0
        if args.attack_class not in (*classes, "all"):
            parser.error("replay requires one manifest class or all")
        selected = (
            classes
            if args.attack_class == "all"
            else {args.attack_class: classes[args.attack_class]}
        )
        codes = [
            replay(name, spec, urls, args.report_dir) for name, spec in selected.items()
        ]
        return max(codes)
    except (SetupError, httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        print(f"Detection setup failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
