#!/usr/bin/env python3
"""Destructive, opt-in process-kill proof for the isolated payments fixture."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time


ROOT = Path(__file__).resolve().parents[4]
FLOW = "payments.instruction-intake"


def run(command, *, env=None):
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=True)
    return result.stdout


def wait_for(check, timeout, description):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(1)
    raise TimeoutError(description)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ns", default="pilot")
    parser.add_argument("--confirm-clean", action="store_true", required=True,
                        help="Delete this flow's rows and purge its input, output and DLQ")
    parser.add_argument("--hold-ms", type=int, default=120000)
    parser.add_argument("--recovery-seconds", type=int, default=90)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,20}", args.ns) or args.hold_ms < 30000:
        parser.error("invalid namespace or hold shorter than 30 seconds")
    env = dict(os.environ, NS=args.ns, REPLAY_UID=str(os.getuid()), REPLAY_GID=str(os.getgid()),
               DOCKER_GID=str(Path("/var/run/docker.sock").stat().st_gid), PAYMENTS_TX_HOLD_MS="0",
               PAYMENTS_COMMIT_HOLD_MS=str(args.hold_ms))
    compose = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.tibco.yml",
               "-p", f"otterworks-tibco-{args.ns}"]
    broker = f"otterworks-tibco-{args.ns}-broker"
    payments = f"otterworks-tibco-{args.ns}-payments"
    db = run(compose + ["ps", "-q", "integration-db"], env=env).strip()
    if not db:
        raise RuntimeError("Start the fixture with make tibco-up first")
    work = Path.home() / ".cache" / "payments-prepare-kill"
    work.mkdir(parents=True, exist_ok=True)
    jars = [Path.home() / ".m2" / "repository" / "org" / "apache" / "activemq" / artifact / "2.40.0"
            / f"{artifact}-2.40.0.jar" for artifact in ("artemis-core-client", "artemis-commons")]
    run(["javac", "--release", "17", "-cp", os.pathsep.join(map(str, jars)), "-d", str(work),
         str(Path(__file__).with_name("ArtemisSnapshot.java"))])
    run(["docker", "exec", broker, "mkdir", "-p", "/tmp/payments-prepare-kill"])
    run(["docker", "cp", str(work / "ArtemisSnapshot.class"), f"{broker}:/tmp/payments-prepare-kill/"])

    def sql(query):
        return run(["docker", "exec", db, "psql", "-U", "replay", "-d", "integration", "-Atc", query]).strip()

    def snapshot():
        output = run(["docker", "exec", broker, "java", "-cp",
                      "/tmp/payments-prepare-kill:/opt/activemq-artemis/lib/*", "ArtemisSnapshot"])
        state = json.loads(next(line.removeprefix("SNAPSHOT ") for line in output.splitlines()
                                if line.startswith("SNAPSHOT ")))
        state["pg_prepared_xacts"] = json.loads(sql(
            "SELECT coalesce(json_agg(row_to_json(t)), '[]'::json) "
            "FROM (SELECT gid, prepared FROM pg_prepared_xacts) t"))
        for table in ("payment_inbox", "payment_ledger"):
            state[table] = json.loads(sql(
                f"SELECT coalesce(json_object_agg(request_id, n), '{{}}'::json) FROM "
                f"(SELECT request_id, count(*) n FROM {table} WHERE flow='{FLOW}' GROUP BY request_id) t"))
        state["status_ids"] = {}
        for message in state.pop("statusMessages"):
            request_id = message.get("requestId")
            state["status_ids"][request_id] = state["status_ids"].get(request_id, 0) + 1
        return state

    run(compose + ["stop", "payments"], env=env)
    initial = snapshot()
    print("STATE BEFORE OBSERVER " + json.dumps(initial, sort_keys=True), flush=True)
    if initial["prepared"] or initial["pg_prepared_xacts"]:
        raise RuntimeError("Refusing to clean while prepared branches exist: " + json.dumps(initial))
    sql(f"DELETE FROM payment_inbox WHERE flow='{FLOW}'; DELETE FROM payment_ledger WHERE flow='{FLOW}'")
    run(["docker", "exec", broker, "sh", "-c",
         'for q in HB.PAYMENT.STATUS HB.PAYMENT.INSTRUCTIONS HB.UNDLV; do '
         './bin/artemis queue purge --url tcp://localhost:61616 --user "$ARTEMIS_USER" '
         '--password "$ARTEMIS_PASSWORD" --name "$q" || exit; done'])
    corpus = json.loads((ROOT / "integration" / "corpus" / FLOW / "flow.json").read_text())
    expected = {message["properties"]["requestId"]: 1 for message in corpus["inputs"]["messages"]}

    def logs():
        return subprocess.run(["docker", "logs", payments], text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, check=True).stdout

    def passed(state):
        return (state["payment_inbox"] == state["payment_ledger"] == state["status_ids"] == expected
                and not state["prepared"] and not state["pg_prepared_xacts"]
                and state["queues"]["HB.PAYMENT.INSTRUCTIONS"]["messageCount"] == 0
                and state["queues"]["HB.UNDLV"]["messageCount"] == 0
                and all(queue["deliveringCount"] == 0 for queue in state["queues"].values())
                and state["queues"]["HB.PAYMENT.STATUS"]["messageCount"] == len(expected))

    try:
        run(compose + ["up", "-d", "--no-deps", "--force-recreate", "payments"], env=env)
        wait_for(lambda: "Started PaymentsApplication" in logs(), 60, "payments startup")
        publisher = (
            "from pathlib import Path; from integration.harness.runner import load_corpus; "
            "from integration.harness.transports import Broker; "
            f"config,flows,_=load_corpus(Path('integration/corpus'),['{FLOW}']); "
            "broker=Broker(config['broker'],[]); broker.open(); "
            "[broker.send(message) for message in flows[0][1]['inputs']['messages']]; broker.close()"
        )
        run(compose + ["run", "--rm", "--no-deps", "--entrypoint", "python", "replay-runner", "-c", publisher], env=env)
        wait_for(lambda: "prepared, holding before status commit xid=" in logs(), 30, "prepared status commit barrier")
        for line in logs().splitlines():
            if "prepared, holding" in line or "Narayana node identifier=" in line:
                print(line, flush=True)
        held_state = snapshot()
        print("STATE AT HOLD " + json.dumps(held_state, sort_keys=True), flush=True)
        if not held_state["prepared"]:
            raise RuntimeError("Barrier did not expose a prepared Artemis branch")
        if not any("in-tx published requestId=" + request_id in logs() for request_id in expected):
            raise RuntimeError("Barrier held an empty transaction rather than a published corpus output")
        run(["docker", "kill", "--signal", "KILL", payments])
        env["PAYMENTS_COMMIT_HOLD_MS"] = "0"
        run(compose + ["up", "-d", "--no-deps", "--force-recreate", "payments"], env=env)
        wait_for(lambda: "Started PaymentsApplication" in logs(), 60, "payments restart")
        state = None
        deadline = time.monotonic() + args.recovery_seconds
        while time.monotonic() < deadline:
            state = snapshot()
            if passed(state):
                break
            time.sleep(2)
        print("STATE AFTER RESTART " + json.dumps(state, sort_keys=True), flush=True)
        print("PAYMENTS RECOVERY LOGS", flush=True)
        for line in logs().splitlines():
            if re.search(r"recover|ARJUNA|tx outcome|node", line, re.IGNORECASE):
                print(line, flush=True)
        print("VERDICT " + ("PASS" if passed(state) else "FAIL"), flush=True)
        return 0 if passed(state) else 1
    finally:
        env["PAYMENTS_COMMIT_HOLD_MS"] = "0"
        env["PAYMENTS_TX_HOLD_MS"] = "0"
        run(compose + ["up", "-d", "--no-deps", "payments"], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
