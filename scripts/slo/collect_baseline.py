#!/usr/bin/env python3
"""Read-only Phase 0 telemetry baseline collector.

Evaluates every PromQL SLI in observability/slo/slo-catalog.yaml against a
Prometheus HTTP API for one day (or any --window) and writes one JSON snapshot
with numerator, denominator, ratio, window and workload per SLI, plus scrape
target health and whether the window held any user traffic. Only GET
/api/v1/query and /api/v1/targets are called; nothing is written to the cluster.

  collect:   collect_baseline.py collect --prometheus http://localhost:9090 \
                 --namespace otterworks-main --out observability/slo/baseline
  summarize: collect_baseline.py summarize observability/slo/baseline
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "observability/slo/slo-catalog.yaml"
BASELINE_DAYS = 30
HEALTH_PATHS = re.compile(r"^(/health.*|/metrics|/ready|/actuator.*|other|health.*|metrics)$")

_KEYWORDS = {"by", "without", "on", "ignoring", "group_left", "group_right",
             "bool", "offset", "and", "or", "unless", "inf", "nan"}
_AGGREGATORS = {"sum", "min", "max", "avg", "count", "stddev", "stdvar", "topk",
                "bottomk", "quantile", "count_values", "group", "limitk", "limit_ratio"}
_IDENT = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:]*")


def scope_namespace(expr: str, namespace: str | None) -> str:
    """Add namespace="<ns>" to every metric selector in a PromQL expression."""
    if not namespace:
        return expr
    matcher = f'namespace="{namespace}"'
    out, i, n = [], 0, len(expr)
    while i < n:
        c = expr[i]
        if c in "\"'":
            j = expr.index(c, i + 1) + 1
            out.append(expr[i:j]); i = j
        elif c == "[":
            j = expr.index("]", i) + 1
            out.append(expr[i:j]); i = j
        elif _IDENT.match(c) and (i == 0 or not (expr[i - 1].isalnum() or expr[i - 1] in "_.")):
            m = _IDENT.match(expr, i)
            word, j = m.group(0), m.end()
            k = j
            while k < n and expr[k] == " ":
                k += 1
            if word in _KEYWORDS:
                out.append(word); i = j
                if word in {"by", "without", "on", "ignoring", "group_left", "group_right"} and k < n and expr[k] == "(":
                    end = expr.index(")", k) + 1
                    out.append(expr[j:end]); i = end
            elif word in _AGGREGATORS or (k < n and expr[k] == "("):
                out.append(word); i = j
            elif k < n and expr[k] == "{":
                end = expr.index("}", k)
                inner = expr[k + 1:end].strip()
                out.append(word + "{" + (f"{matcher},{inner}" if inner else matcher) + "}")
                i = end + 1
            else:
                out.append(word + "{" + matcher + "}"); i = j
        else:
            out.append(c); i += 1
    return "".join(out)


def load_catalog(path: Path = CATALOG) -> dict:
    return yaml.safe_load(path.read_text())


def promql_slis(catalog: dict) -> list[dict]:
    return [s for s in catalog["slis"] if s.get("promql", True)]


class Prometheus:
    def __init__(self, url: str, timeout: float = 30.0):
        self.url, self.timeout = url.rstrip("/"), timeout

    def get(self, path: str, **params) -> dict:
        q = urllib.parse.urlencode(params)
        with urllib.request.urlopen(f"{self.url}{path}?{q}", timeout=self.timeout) as r:
            body = json.load(r)
        if body.get("status") != "success":
            raise RuntimeError(f"{path}: {body.get('error')}")
        return body["data"]

    def scalar(self, expr: str, at: float, counting: bool = True) -> float | None:
        """Event counts are summed across series; gauges and quantiles take the worst (max) series."""
        values = [float(r["value"][1]) for r in self.get("/api/v1/query", query=expr, time=at)["result"]]
        values = [v for v in values if not math.isnan(v)]
        if not values:
            return None
        return sum(values) if counting else max(values)

    def vector(self, expr: str, at: float) -> list[dict]:
        return [{"labels": r["metric"], "value": float(r["value"][1])}
                for r in self.get("/api/v1/query", query=expr, time=at)["result"]]


def is_counting(sli: dict) -> bool:
    """True when numerator/denominator are event rates to turn into event counts over the window."""
    expr = sli["numerator"]
    return "rate(" in expr and "histogram_quantile" not in expr and " / " not in expr and sli["kind"] != "saturation"


def _as_increase(expr: str) -> str:
    """rate(x[w]) -> increase(x[w]) so numerators/denominators are event counts."""
    return re.sub(r"\brate\(", "increase(", expr)


def collect(prom: Prometheus, catalog: dict, namespace: str | None, window: str, at: float) -> dict:
    slis = []
    for sli in promql_slis(catalog):
        entry = {k: sli.get(k) for k in ("id", "service", "owner", "kind", "objective", "workload", "instrumented")}
        entry["window"] = window
        try:
            counting = is_counting(sli)

            def query(template: str) -> str:
                expr = scope_namespace(template.replace("$window", window), namespace)
                return _as_increase(expr) if counting else expr

            entry["numerator_query"] = query(sli["numerator"])
            entry["numerator"] = prom.scalar(entry["numerator_query"], at, counting)
            if sli.get("denominator"):
                entry["denominator_query"] = query(sli["denominator"])
                entry["denominator"] = prom.scalar(entry["denominator_query"], at, counting)
                if entry["denominator"] is not None and entry["numerator"] is None:
                    entry["numerator"] = 0.0
                num, den = entry["numerator"], entry["denominator"]
                entry["ratio"] = (num / den) if num is not None and den else None
            if entry["numerator"] is None:
                entry["status"] = "no_data"
            elif sli.get("denominator") and not entry["denominator"]:
                entry["status"] = "no_events"
            else:
                entry["status"] = "measured"
        except Exception as exc:  # noqa: BLE001 - one bad query must not drop the snapshot
            entry["status"], entry["error"] = "query_error", str(exc)
        slis.append(entry)

    ns = f',namespace="{namespace}"' if namespace else ""
    targets = prom.vector(f'up{{namespace!=""{ns}}}', at)
    traffic = prom.vector(scope_namespace(
        f"sum by (job, path) (increase(api_gateway_http_requests_total[{window}]))", namespace), at)
    user_requests = sum(t["value"] for t in traffic if not HEALTH_PATHS.match(t["labels"].get("path", "")))
    runtime = prom.get("/api/v1/status/runtimeinfo")
    return {
        "schema": 1,
        "collected_at": dt.datetime.fromtimestamp(at, dt.timezone.utc).isoformat(),
        "prometheus": prom.url,
        "environment": catalog.get("environment_of_record"),
        "namespace": namespace,
        "window": window,
        "prometheus_retention": runtime.get("storageRetention"),
        "targets": sorted(({"job": t["labels"].get("job"), "up": t["value"] == 1.0} for t in targets),
                          key=lambda t: t["job"] or ""),
        "gateway_user_requests": user_requests,
        "workload": "user traffic" if user_requests > 0 else "health/scrape only (not representative)",
        "slis": slis,
    }


def summarize(directory: Path) -> dict:
    """Roll daily snapshots up into the 30-day baseline (sums of counts, not averages of ratios)."""
    snaps = [json.loads(p.read_text()) for p in sorted(directory.glob("baseline-*.json"))]
    days = sorted({s["collected_at"][:10] for s in snaps})
    per_sli: dict[str, dict] = {}
    for snap in snaps:
        for s in snap["slis"]:
            agg = per_sli.setdefault(s["id"], {"numerator": 0.0, "denominator": 0.0, "days_measured": 0})
            if s.get("status") == "measured" and s.get("denominator") is not None:
                agg["numerator"] += s["numerator"] or 0.0
                agg["denominator"] += s["denominator"] or 0.0
                agg["days_measured"] += 1
    for agg in per_sli.values():
        agg["ratio"] = agg["numerator"] / agg["denominator"] if agg["denominator"] else None
    user_days = sum(1 for s in snaps if s.get("gateway_user_requests", 0) > 0)
    return {
        "days_collected": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "days_with_user_traffic": user_days,
        "baseline_complete": len(days) >= BASELINE_DAYS and user_days >= BASELINE_DAYS,
        "slis": per_sli,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--prometheus", default="http://localhost:9090")
    c.add_argument("--namespace", default="otterworks-main")
    c.add_argument("--window", default="1d")
    c.add_argument("--out", type=Path, default=ROOT / "observability/slo/baseline")
    c.add_argument("--at", type=float, default=None, help="evaluation time (unix seconds), default now")
    s = sub.add_parser("summarize")
    s.add_argument("directory", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "summarize":
        json.dump(summarize(args.directory), sys.stdout, indent=2)
        print()
        return 0
    at = args.at or dt.datetime.now(dt.timezone.utc).timestamp()
    snap = collect(Prometheus(args.prometheus), load_catalog(), args.namespace or None, args.window, at)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"baseline-{snap['collected_at'][:10]}-{args.namespace or 'all'}.json"
    path.write_text(json.dumps(snap, indent=2) + "\n")
    measured = sum(1 for s in snap["slis"] if s["status"] == "measured")
    print(f"{path}: {measured}/{len(snap['slis'])} SLIs measured; workload={snap['workload']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
