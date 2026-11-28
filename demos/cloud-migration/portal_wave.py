import argparse
import hashlib
import http.client
import json
import math
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


LOOPBACK = "127.0.0.1"
ADAPTERS = ("java", "serverless")
TARGET_HEADER = "X-Portal-Wave-Target"
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "proxy-connection",
}


def valid_port(port):
    return type(port) is int and 0 < port <= 65535


def local_path(path):
    return (path.startswith("/") and not path.startswith("//")
            and not any(c in "\\#" or ord(c) <= 32 or ord(c) == 127 for c in path))


@dataclass(frozen=True)
class Target:
    port: int
    identity: str
    identity_path: str


@dataclass(frozen=True)
class Plan:
    run_token: str
    router_port: int
    java: Target
    serverless: Target
    health_path: str
    window_ms: int
    interval_ms: int
    timeout_ms: int
    max_error_rate: float
    max_p95_ms: float

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_]{3,40}", self.run_token):
            raise ValueError("invalid run token")
        ports = (self.router_port, self.java.port, self.serverless.port)
        if not all(map(valid_port, ports)) or len(set(ports)) != 3:
            raise ValueError("router and upstreams need distinct loopback ports")
        if self.java.identity == self.serverless.identity:
            raise ValueError("target identities must be distinct")
        for target in (self.java, self.serverless):
            if not re.fullmatch(r"[A-Za-z0-9_.:@/-]{1,200}", target.identity) or not local_path(target.identity_path):
                raise ValueError("invalid target identity or path")
        if not local_path(self.health_path):
            raise ValueError("invalid health path")
        times = (self.timeout_ms, self.interval_ms, self.window_ms)
        if any(type(ms) is not int for ms in times) or not 0 < self.timeout_ms < self.interval_ms <= self.window_ms:
            raise ValueError("require 0 < timeout < interval <= window")
        if self.window_ms % self.interval_ms:
            raise ValueError("window must be a multiple of interval")
        if not 0 <= self.max_error_rate <= 1 or not math.isfinite(self.max_p95_ms) or self.max_p95_ms <= 0:
            raise ValueError("invalid error rate or p95 threshold")

    @classmethod
    def read(cls, path):
        data = json.loads(path.read_text())
        for name in ADAPTERS:
            data[name] = Target(**data[name])
        return cls(**data)


class Route:
    def __init__(self, plan, state_root):
        self.plan = plan
        self.directory = state_root / plan.run_token
        self.active = self.directory / "active"
        self.frozen = self.directory / "frozen.json"

    def initialize(self):
        self.directory.mkdir(mode=0o700)
        self.active.write_text("java")

    def selected(self):
        name = self.active.read_text()
        if name not in ADAPTERS:
            raise ValueError("invalid active adapter")
        return name

    def select(self, name):
        if name not in ADAPTERS:
            raise ValueError("invalid adapter")
        fd, temporary = tempfile.mkstemp(dir=self.directory)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(name)
            os.replace(temporary, self.active)
        finally:
            Path(temporary).unlink(missing_ok=True)


def forward_headers(headers):
    excluded = HOP_HEADERS | {"content-length", TARGET_HEADER.lower()}
    excluded = excluded.union(
        token.strip().lower()
        for name, value in headers if name.lower() == "connection"
        for token in value.split(",")
    )
    return [(name, value) for name, value in headers if name.lower() not in excluded]


def make_router(route, log):
    plan = route.plan

    class Handler(BaseHTTPRequestHandler):
        def proxy(self):
            if not local_path(self.path):
                self.send_error(400)
                return
            if self.headers.get("Transfer-Encoding"):
                self.send_error(501)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0:
                    raise ValueError()
            except ValueError:
                self.send_error(400)
                return
            name = route.selected()
            target = getattr(plan, name)
            connection = http.client.HTTPConnection(LOOPBACK, target.port, timeout=plan.timeout_ms / 1000)
            try:
                body = self.rfile.read(length) if length else None
                connection.putrequest(self.command, self.path, skip_accept_encoding=True)
                for key, value in forward_headers(self.headers.items()):
                    if key.lower() != "host":
                        connection.putheader(key, value)
                if body is not None or self.headers.get("Content-Length") is not None:
                    connection.putheader("Content-Length", str(length))
                connection.endheaders(body)
                upstream = connection.getresponse()
                status = upstream.status
                headers = forward_headers(upstream.getheaders())
                payload = upstream.read()
            except (OSError, http.client.HTTPException):
                status, headers, payload = 502, [], b""
            finally:
                connection.close()

            log({"run_token": plan.run_token, "adapter": name, "target_identity": target.identity, "status": status})
            self.send_response_only(status)
            for key, value in headers:
                self.send_header(key, value)
            self.send_header(TARGET_HEADER, target.identity)
            if self.command == "HEAD":
                if status != 502 and upstream.getheader("Content-Length") is not None:
                    self.send_header("Content-Length", upstream.getheader("Content-Length"))
            elif status not in (204, 304):
                self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = proxy

        def log_message(self, *_args):
            pass

    return ThreadingHTTPServer((LOOPBACK, plan.router_port), Handler)


def request(port, path, timeout):
    started = time.monotonic()
    connection = http.client.HTTPConnection(LOOPBACK, port, timeout=timeout)
    try:
        connection.request("GET", path, headers={"Cache-Control": "no-cache"})
        response = connection.getresponse()
        body = response.read()
        status, identity = response.status, response.getheader(TARGET_HEADER)
    except (OSError, http.client.HTTPException):
        status, identity, body = None, None, b""
    finally:
        connection.close()
    return status, identity, body, (time.monotonic() - started) * 1000


def verify_endpoint(route, adapter, expected_hash=None):
    plan = route.plan
    target = getattr(plan, adapter)
    direct, routed = (
        request(port, target.identity_path, plan.timeout_ms / 1000)[:3]
        for port in (target.port, plan.router_port)
    )
    body_hash = hashlib.sha256(routed[2]).hexdigest() if routed[0] == 200 else None
    verified = (direct[0] == routed[0] == 200 and routed[1] == target.identity and direct[2] == routed[2]
                and (expected_hash is None or body_hash == expected_hash))
    return {
        "status": "passed" if verified else "failed",
        "target_identity": routed[1],
        "direct_status": direct[0],
        "routed_status": routed[0],
        "body_sha256": body_hash,
    }


def sample(plan, adapter):
    expected = getattr(plan, adapter).identity
    started = time.monotonic()
    count = plan.window_ms // plan.interval_ms
    errors, latencies, identities = 0, [], set()
    for index in range(count):
        deadline = started + index * plan.interval_ms / 1000
        time.sleep(max(0, deadline - time.monotonic()))
        budget = min(plan.timeout_ms / 1000, deadline + plan.interval_ms / 1000 - time.monotonic())
        status, identity, _, latency = (
            request(plan.router_port, plan.health_path, budget) if budget > 0 else (None, None, b"", 0)
        )
        if identity is not None:
            identities.add(identity)
        if status is not None or budget > 0:
            latencies.append(latency)
        if status != 200 or identity != expected or latency > plan.timeout_ms:
            errors += 1
    time.sleep(max(0, started + plan.window_ms / 1000 - time.monotonic()))
    p95 = sorted(latencies)[math.ceil(len(latencies) * .95) - 1] if latencies else None
    passed = errors / count <= plan.max_error_rate and p95 is not None and p95 <= plan.max_p95_ms
    passed = passed and identities == {expected}
    return {
        "status": "passed" if passed else "failed",
        "expected_target": expected,
        "observed_targets": sorted(identities),
        "samples": count,
        "errors": errors,
        "error_rate": errors / count,
        "p95_ms": p95,
        "estimated_downtime_ms": errors * plan.interval_ms,
        "elapsed_ms": (time.monotonic() - started) * 1000,
    }


def freeze(route):
    if route.frozen.exists():
        raise ValueError("already frozen for this run token")
    prior = verify_endpoint(route, "java")
    plan = route.plan
    status, _, body, _ = request(plan.serverless.port, plan.serverless.identity_path, plan.timeout_ms / 1000)
    candidate_identity = {
        "status": "passed" if status == 200 else "failed",
        "target_identity": plan.serverless.identity,
        "body_sha256": hashlib.sha256(body).hexdigest() if status == 200 else None,
    }
    baseline = sample(route.plan, "java")
    frozen = {
        "plan": asdict(plan), "selected_adapter": "serverless", "prior": prior,
        "candidate_identity": candidate_identity, "baseline": baseline,
    }
    with route.frozen.open("x") as stream:
        json.dump(frozen, stream, indent=2)
    return frozen


def verified_frozen(route):
    raw = route.frozen.read_bytes()
    frozen = json.loads(raw)
    if frozen["plan"] != asdict(route.plan) or frozen["selected_adapter"] != "serverless":
        raise ValueError("plan differs from the frozen configuration")
    if any(frozen[gate]["status"] != "passed" for gate in ("prior", "candidate_identity", "baseline")):
        raise ValueError("endpoint identities and baseline must pass before a switch")
    return frozen, hashlib.sha256(raw).hexdigest()


def rehearse(route):
    frozen, frozen_hash = verified_frozen(route)
    prior_hash = frozen["prior"]["body_sha256"]
    if route.selected() != "java" or verify_endpoint(route, "java", prior_hash)["status"] != "passed":
        raise ValueError("expected the verified prior endpoint before switching")
    started = time.monotonic()
    try:
        route.select("serverless")
        candidate = sample(route.plan, "serverless")
        candidate_endpoint = verify_endpoint(route, "serverless", frozen["candidate_identity"]["body_sha256"])
    finally:
        rollback_started = time.monotonic()
        route.select("java")
    prior = verify_endpoint(route, "java", prior_hash)
    endpoint_checked = time.monotonic()
    recovered = sample(route.plan, "java")
    finished = time.monotonic()
    return {
        "run_token": route.plan.run_token,
        "frozen_sha256": frozen_hash,
        "candidate": candidate,
        "candidate_endpoint": candidate_endpoint,
        "rollback_reason": (
            "planned-drill" if candidate["status"] == candidate_endpoint["status"] == "passed" else "gate-trip"
        ),
        "prior_restored": prior,
        "recovered": recovered,
        "recovery_status": "passed" if prior["status"] == recovered["status"] == "passed" else "failed",
        "prior_endpoint_check_elapsed_ms": (endpoint_checked - rollback_started) * 1000,
        "rollback_elapsed_ms": (finished - rollback_started) * 1000,
        "elapsed_ms": (finished - started) * 1000,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("serve", "freeze", "switch", "rollback", "rehearse"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    route = Route(Plan.read(args.plan), args.state_root)
    if args.command == "serve":
        with make_router(route, lambda record: print(json.dumps(record), flush=True)) as server:
            route.initialize()
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return
    if args.command in ("switch", "rollback"):
        adapter = "serverless" if args.command == "switch" else "java"
        if adapter == "serverless":
            frozen, _ = verified_frozen(route)
            if verify_endpoint(route, "java", frozen["prior"]["body_sha256"])["status"] != "passed":
                raise ValueError("expected the verified prior endpoint before switching")
        route.select(adapter)
        result = {"run_token": route.plan.run_token, "adapter": adapter, "target_identity": getattr(route.plan, adapter).identity}
    else:
        result = freeze(route) if args.command == "freeze" else rehearse(route)
    print(json.dumps(result, indent=2))
    if (result.get("recovery_status") == "failed"
            or result.get("rollback_reason") == "gate-trip"
            or result.get("candidate_identity", {}).get("status") == "failed"
            or result.get("prior", {}).get("status") == "failed"
            or result.get("baseline", {}).get("status") == "failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
