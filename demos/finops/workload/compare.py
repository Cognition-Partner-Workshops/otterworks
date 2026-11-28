import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from math import ceil
from threading import Thread
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

REQUESTS = tuple({"request_id": i, "scratch_gib": i % 8} for i in range(100))
RESERVED_GIB = 27
MIN_APP_DAYS = 7
AUDIT_DAYS = 90
MAX_ERROR_RATE = 0.01
MAX_MODELED_P95_MS = 20


def simulate(settings, request):
    required_gib = RESERVED_GIB + request["scratch_gib"]
    disk_pressure = settings["root_volume_gib"] < required_gib
    modeled_ms = (40 if disk_pressure else 9) + request["request_id"] % 7
    return {
        "disk_pressure": disk_pressure,
        "modeled_latency_ms": modeled_ms,
    }


def handler_for(settings):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            result = simulate(settings, json.loads(body))
            self.send_response(507 if result["disk_pressure"] else 200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        def log_message(self, *_):
            pass

    return Handler


def p95(samples):
    return sorted(samples)[ceil(0.95 * len(samples)) - 1]


def measure(settings):
    bodies = [json.dumps(request).encode() for request in REQUESTS]
    modeled_ms, wall_ms, errors, pressure = [], [], 0, 0
    opener = build_opener(ProxyHandler({}))
    with HTTPServer(("127.0.0.1", 0), handler_for(settings)) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for body in bodies:
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                started = perf_counter()
                try:
                    response = opener.open(request, timeout=5)
                except HTTPError as exc:
                    response = exc
                with response:
                    result = json.load(response)
                    errors += response.code >= 400
                wall_ms.append((perf_counter() - started) * 1000)
                modeled_ms.append(result["modeled_latency_ms"])
                pressure += result["disk_pressure"]
        finally:
            server.shutdown()
            thread.join()

    error_rate = errors / len(bodies)
    latency = p95(modeled_ms)
    gates = {
        "error_rate_at_most_1_percent": error_rate <= MAX_ERROR_RATE,
        "modeled_p95_at_most_20_ms": latency <= MAX_MODELED_P95_MS,
        "no_disk_pressure": pressure == 0,
        "minimum_app_retention_preserved": settings["app_retention_days"] >= MIN_APP_DAYS,
        "audit_policy_unchanged": settings["audit_retention_days"] == AUDIT_DAYS,
    }
    return {
        "source": "local HTTP workload with modeled disk and latency",
        "settings": settings,
        "requests": len(bodies),
        "workload_sha256": hashlib.sha256(b"\n".join(bodies)).hexdigest(),
        "errors": errors,
        "error_rate": error_rate,
        "modeled_p95_ms": latency,
        "loopback_p95_ms_informational": round(p95(wall_ms), 3),
        "disk_pressure_responses": pressure,
        "gates": gates,
        "health": "pass" if all(gates.values()) else "fail",
    }


def main():
    parser = argparse.ArgumentParser(description="Run 100 matched local HTTP requests against modeled dev settings")
    for option in ("root-volume-gib", "app-retention-days", "audit-retention-days"):
        parser.add_argument(f"--{option}", type=int, required=True)
    result = measure(vars(parser.parse_args()))
    print(json.dumps(result, indent=2))
    return int(result["health"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
