#!/usr/bin/env python3
"""Drive an MCP stdio launcher like a client would: initialize, list tools, run read-only calls.

usage: scripts/mcp-smoke.py grafana|postgres
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CALLS = {
    "grafana": [("search_dashboards", {"query": "Collection"}), ("list_datasources", {})],
    "postgres": [
        ("execute_sql", {"sql": "SELECT status, count(*) FROM collection.job_runs GROUP BY 1 ORDER BY 1"}),
        ("execute_sql", {"sql": "INSERT INTO collection.sources VALUES (99, 'x', 'stream', 't')"}),
        ("list_schemas", {}),
    ],
}


def main() -> int:
    which = sys.argv[1]
    proc = subprocess.Popen(
        ["bash", str(HERE / "mcp" / f"{which}-stdio.sh")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    assert proc.stdin and proc.stdout
    n = 0

    def rpc(method: str, params: dict, notify: bool = False) -> dict | None:
        nonlocal n
        msg: dict = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            n += 1
            msg["id"] = n
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        if notify:
            return None
        while True:
            line = proc.stdout.readline()
            if not line:
                raise SystemExit(f"{which}: server closed stdout")
            data = json.loads(line)
            if data.get("id") == n:
                return data

    init = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "collection-smoke", "version": "0"}})
    print(which, "server:", init["result"]["serverInfo"])
    rpc("notifications/initialized", {}, notify=True)
    tools = [t["name"] for t in rpc("tools/list", {})["result"]["tools"]]
    print(which, "tools:", len(tools), "write-like:", sorted(t for t in tools if t.split("_")[0] in ("create", "update", "delete", "patch", "add")))
    for name, args in CALLS[which]:
        res = rpc("tools/call", {"name": name, "arguments": args})
        body = res.get("result") or res.get("error")
        text = json.dumps(body)[:300]
        print(f"{which} {name} {json.dumps(args)[:80]} -> {text}")
    proc.stdin.close()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=15)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
