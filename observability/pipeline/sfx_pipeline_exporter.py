"""Prometheus HTTP exporter backed by the shared Snowflake pipeline checks."""
import argparse
import os
from pathlib import Path
import sys
import time

from prometheus_client import CollectorRegistry, Gauge, start_http_server

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "warehouse/pipeline"))
from checks import MODEL, RUN, add_arguments, run_checks, thresholds


class Exporter:
    def __init__(self, registry=None):
        self.registry = registry if registry is not None else CollectorRegistry()
        self.gauges = {}
        for name, labels in (("load_errors", []), ("rows", ["day"]),
                             ("row_count_drop_ratio", []), ("null_ratio", ["column"]),
                             ("check_firing", ["check"]), ("last_scrape_success", [])):
            self.gauges[name] = Gauge("sfx_pipeline_" + name, name.replace("_", " "),
                                     ["run", "model", *labels], registry=self.registry)

    def set(self, name, value, *labels):
        self.gauges[name].labels(RUN, MODEL, *labels).set(value)

    def refresh(self, limits, checker=run_checks):
        try:
            result = checker(limits)
        except Exception:
            self.set("last_scrape_success", 0)
            print("Pipeline checks refresh failed", file=sys.stderr, flush=True)
            return False
        self.set("load_errors", result["load_errors"])
        for day, count in result["rows"].items():
            self.set("rows", count, day)
        self.set("row_count_drop_ratio", result["checks"]["row_count_drop"]["value"])
        for column, ratio in result["null_ratios"].items():
            self.set("null_ratio", ratio, column)
        for name, check in result["checks"].items():
            self.set("check_firing", int(check["firing"]), name)
        self.set("last_scrape_success", 1)
        return True


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    parser.add_argument("--port", type=int, default=int(os.getenv("SFX_EXPORTER_PORT", "9471")))
    parser.add_argument("--interval", type=float, default=float(os.getenv("SFX_REFRESH_SECONDS", "30")))
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("interval must be positive")
    limits = thresholds(args)
    exporter = Exporter()
    exporter.refresh(limits)
    start_http_server(args.port, registry=exporter.registry)
    print(f"Pipeline exporter ready on {args.port}", flush=True)
    while True:
        time.sleep(args.interval)
        exporter.refresh(limits)


if __name__ == "__main__":
    main()
