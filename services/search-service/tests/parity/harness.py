"""Replayable black-box parity harness for the search service.

Drives a running service over HTTP (plus a few environment control steps via
Docker Compose) and records, per case, the request and the normalised
response: status, the headers that matter and the body.

    python -m tests.parity.harness record --base-url http://localhost:8087
    python -m tests.parity.harness replay --base-url http://localhost:8087

``record`` runs ``cases.CASES`` and writes the transcript and metrics dump.
``replay`` re-sends the requests stored in the transcript (not ``cases.py``),
normalises the new responses the same way and diffs them against the stored
ones. It exits 1 if anything differs.
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import http.client
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
DEFAULT_TRANSCRIPT = HERE / "flask_transcript.json"
DEFAULT_METRICS = HERE / "flask_metrics.json"
DEFAULT_COMPOSE = (
    "docker compose -f docker-compose.infra.yml -f docker-compose.yml "
    "-f services/search-service/tests/parity/compose.parity.yml"
)

METRIC_FAMILIES = (
    "search_service_requests_total",
    "search_service_request_duration_seconds",
    "search_service_searches_total",
    "search_service_index_operations_total",
)

# Comma-separated headers whose token order carries no meaning.
UNORDERED_LIST_HEADERS = {
    "allow",
    "vary",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-expose-headers",
}
RECORDED_HEADERS = {"content-type", "location", "allow", "vary"}

VOLATILE = "<volatile>"


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #


def normalise_headers(headers: list[tuple[str, str]], base_url: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in headers:
        key = name.lower()
        if key not in RECORDED_HEADERS and not key.startswith("access-control-"):
            continue
        if key in UNORDERED_LIST_HEADERS:
            value = ", ".join(sorted(t.strip() for t in value.split(",") if t.strip()))
        if key == "location":
            value = value.replace(base_url.rstrip("/"), "<base-url>")
        out[key] = value if key not in out else f"{out[key]}, {value}"
    return dict(sorted(out.items()))


def summarise_metrics_text(text: str) -> dict[str, Any]:
    """Reduce a Prometheus exposition to its deterministic parts.

    Sample values that depend on wall-clock time (``*_created``, histogram
    ``_bucket``/``_sum``) are replaced with a placeholder; counters and
    histogram ``_count`` keep their values.
    """
    types: dict[str, str] = {}
    helps: dict[str, str] = {}
    samples: dict[str, list[dict[str, Any]]] = {f: [] for f in METRIC_FAMILIES}
    label_re = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')

    for line in text.splitlines():
        if line.startswith("# TYPE "):
            _, _, name, mtype = line.split(" ", 3)
            types[name] = mtype
            continue
        if line.startswith("# HELP "):
            _, _, name, *rest = line.split(" ", 3)
            helps[name] = rest[0] if rest else ""
            continue
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{.*\})?\s+(\S+)", line)
        if not m:
            continue
        sample_name, label_blob, raw_value = m.groups()
        family = next((f for f in METRIC_FAMILIES if _belongs(sample_name, f)), None)
        if family is None:
            continue
        labels = dict(label_re.findall(label_blob or ""))
        suffix = sample_name[len(_base(family)) :]
        if suffix in ("_created", "_bucket", "_sum"):
            value: Any = VOLATILE
        else:
            num = float(raw_value)
            value = int(num) if num.is_integer() else num
        samples[family].append(
            {
                "name": sample_name,
                "labels": dict(sorted(labels.items())),
                "value": value,
            }
        )

    families: dict[str, Any] = {}
    for family in METRIC_FAMILIES:
        base = _base(family)
        fam_samples = sorted(
            samples[family], key=lambda s: (s["name"], sorted(s["labels"].items()))
        )
        label_values: dict[str, set[str]] = {}
        for s in fam_samples:
            for k, v in s["labels"].items():
                if k == "le":
                    continue
                label_values.setdefault(k, set()).add(v)
        families[family] = {
            "present": base in types or family in types,
            "type": types.get(base) or types.get(family),
            "help": helps.get(base) or helps.get(family),
            "label_names": sorted(label_values),
            "label_values": {k: sorted(v) for k, v in sorted(label_values.items())},
            "samples": fam_samples,
        }
    return families


def _base(family: str) -> str:
    return family.removesuffix("_total")


def _belongs(sample_name: str, family: str) -> bool:
    base = _base(family)
    return sample_name in (family, base) or (
        sample_name.startswith(base + "_")
        and sample_name[len(base) :]
        in ("_total", "_created", "_bucket", "_sum", "_count")
    )


def normalise_body(path: str, status: int, content_type: str, raw: bytes) -> Any:
    if path.split("?")[0] == "/metrics" and status == 200:
        summary = summarise_metrics_text(raw.decode("utf-8"))
        return {
            "metrics_families_present": sorted(
                f for f, v in summary.items() if v["present"]
            )
        }
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    if "json" in content_type:
        try:
            return {"json": json.loads(text)}
        except ValueError:
            pass
    return {"text": text}


# --------------------------------------------------------------------------- #
# HTTP + control
# --------------------------------------------------------------------------- #


def request_from_case(case: dict[str, Any]) -> dict[str, Any]:
    req: dict[str, Any] = {
        "method": case["method"],
        "path": case["path"],
        "headers": case["headers"],
    }
    if "json" in case:
        req["body"] = json.dumps(case["json"])
    elif "raw" in case:
        req["body"] = case["raw"]
    return req


def send(base_url: str, req: dict[str, Any]) -> dict[str, Any]:
    url = urllib.parse.urlsplit(base_url)
    conn = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=60)
    body = req.get("body")
    try:
        conn.request(
            req["method"],
            req["path"],
            body=body.encode() if body is not None else None,
            headers=req["headers"],
        )
        resp = conn.getresponse()
        raw = resp.read()
        headers = resp.getheaders()
    finally:
        conn.close()
    content_type = resp.getheader("Content-Type", "") or ""
    return {
        "status": resp.status,
        "headers": normalise_headers(headers, base_url),
        "body": normalise_body(req["path"], resp.status, content_type, raw),
        "_raw": raw,
    }


class Control:
    def __init__(self, compose: str, base_url: str, meili_url: str) -> None:
        self.compose = shlex.split(compose)
        self.base_url = base_url
        self.meili_url = meili_url

    def _run(self, *args: str) -> None:
        subprocess.run(
            [*self.compose, *args],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def run(self, step: dict[str, Any]) -> None:
        action = step["action"]
        if action == "redis_set":
            self._run(
                "exec", "-T", "redis", "redis-cli", "SET", step["key"], step["value"]
            )
        elif action == "redis_del":
            self._run("exec", "-T", "redis", "redis-cli", "DEL", step["key"])
        elif action == "restart_service":
            self._run("restart", "search-service")
            _wait_http_ok(f"{self.base_url.rstrip('/')}/health")
        elif action == "stop_meilisearch":
            self._run("stop", "meilisearch")
        elif action == "start_meilisearch":
            self._run("start", "meilisearch")
            _wait_http_ok(f"{self.meili_url.rstrip('/')}/health")
        else:
            raise ValueError(f"unknown action {action!r}")


def _wait_http_ok(url: str, timeout: float = 90.0) -> None:
    # Polls only /health (search-service excludes it from request metrics) or
    # MeiliSearch directly, so waiting never changes recorded counters.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with contextlib.suppress(OSError), urllib.request.urlopen(url, timeout=2) as r:
            if r.status == 200:
                return
        time.sleep(0.5)
    raise TimeoutError(f"{url} not healthy after {timeout}s")


# --------------------------------------------------------------------------- #
# Record / replay
# --------------------------------------------------------------------------- #


def execute(
    entries: list[dict[str, Any]], base_url: str, control: Control
) -> tuple[list[dict[str, Any]], dict]:
    transcript: list[dict[str, Any]] = []
    metrics_dump: dict[str, Any] = {}
    for entry in entries:
        if "action" in entry:
            control.run(entry)
            transcript.append({k: v for k, v in entry.items()})
            continue
        req = entry["request"]
        resp = send(base_url, req)
        raw = resp.pop("_raw")
        if entry["name"] == "metrics.final" and resp["status"] == 200:
            metrics_dump = summarise_metrics_text(raw.decode("utf-8"))
        transcript.append({"name": entry["name"], "request": req, "response": resp})
    return transcript, metrics_dump


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def cmd_record(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(HERE))
    from cases import CASES  # type: ignore[import-not-found]

    entries = [
        c if "action" in c else {"name": c["name"], "request": request_from_case(c)}
        for c in CASES
    ]
    names = [e["name"] for e in entries]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise SystemExit(f"duplicate case names: {sorted(dupes)}")
    control = Control(args.compose, args.base_url, args.meili_url)
    transcript, metrics_dump = execute(entries, args.base_url, control)
    Path(args.transcript).write_text(_dump(transcript))
    Path(args.metrics).write_text(_dump(metrics_dump))
    http_cases = sum(1 for e in transcript if "request" in e)
    print(
        f"recorded {http_cases} HTTP cases + {len(transcript) - http_cases} control steps "
        f"-> {args.transcript}, {args.metrics}"
    )
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    expected = json.loads(Path(args.transcript).read_text())
    expected_metrics = json.loads(Path(args.metrics).read_text())
    control = Control(args.compose, args.base_url, args.meili_url)
    actual, actual_metrics = execute(expected, args.base_url, control)

    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "replay_transcript.json").write_text(_dump(actual))
        (out / "replay_metrics.json").write_text(_dump(actual_metrics))

    diffs = 0
    http_cases = 0
    for exp, act in zip(expected, actual):
        if "request" not in exp:
            continue
        http_cases += 1
        if exp["response"] != act["response"]:
            diffs += 1
            print(
                f"--- DIFF {exp['name']}: {exp['request']['method']} {exp['request']['path']}"
            )
            sys.stdout.writelines(
                difflib.unified_diff(
                    _dump(exp["response"]).splitlines(keepends=True),
                    _dump(act["response"]).splitlines(keepends=True),
                    fromfile="expected",
                    tofile="actual",
                )
            )
    metrics_diff = expected_metrics != actual_metrics
    if metrics_diff:
        print("--- DIFF metrics dump")
        sys.stdout.writelines(
            difflib.unified_diff(
                _dump(expected_metrics).splitlines(keepends=True),
                _dump(actual_metrics).splitlines(keepends=True),
                fromfile="expected",
                tofile="actual",
            )
        )
    print(
        f"replayed {http_cases} HTTP cases: {diffs} differing; metrics dump: "
        f"{'DIFFERS' if metrics_diff else 'identical'}"
    )
    return 1 if diffs or metrics_diff else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("record", "replay"):
        p = sub.add_parser(name)
        p.add_argument(
            "--base-url", default=os.getenv("PARITY_BASE_URL", "http://localhost:8087")
        )
        p.add_argument(
            "--meili-url",
            default=os.getenv("PARITY_MEILI_URL", "http://localhost:7700"),
        )
        p.add_argument(
            "--compose",
            default=os.getenv("PARITY_COMPOSE", DEFAULT_COMPOSE),
            help="compose command (run from repo root) used for control steps",
        )
        p.add_argument("--transcript", default=str(DEFAULT_TRANSCRIPT))
        p.add_argument("--metrics", default=str(DEFAULT_METRICS))
        if name == "replay":
            p.add_argument(
                "--out-dir", help="also write the replayed transcript/metrics here"
            )
    args = parser.parse_args(argv)
    return cmd_record(args) if args.cmd == "record" else cmd_replay(args)


if __name__ == "__main__":
    raise SystemExit(main())
