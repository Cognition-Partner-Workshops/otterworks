import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
import urllib.request
import zlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["up", "down"])
    parser.add_argument("namespace")
    parser.add_argument("--settings", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.namespace):
        parser.error("namespace must contain only letters, digits, underscores or hyphens")
    root = Path(__file__).resolve().parent
    app = root / "iri-api"
    settings = args.settings.resolve() if args.settings else app / ".mvn" / "settings.xml"
    state = root / ".state" / args.namespace
    state.mkdir(parents=True, exist_ok=True)
    pid_file = state / "iri-api.pid"
    log_file = state / "iri-api.log"
    jar = app / "target" / "iri-api-1.0.0.jar"
    offset = zlib.crc32(args.namespace.encode()) % 1000
    port = 19080 + offset
    url = f"http://127.0.0.1:{port}"
    pid = int(pid_file.read_text()) if pid_file.exists() else None
    running = pid is not None and Path(f"/proc/{pid}/cmdline").exists() and str(jar).encode() in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    sources = [app / "pom.xml", *list((app / "src" / "main").rglob("*"))]
    stale = not jar.exists() or any(p.is_file() and p.stat().st_mtime > jar.stat().st_mtime for p in sources)
    if args.action == "down" or (running and stale):
        if running:
            os.kill(pid, signal.SIGTERM)
            for _ in range(100):
                if not Path(f"/proc/{pid}/cmdline").exists() or not Path(f"/proc/{pid}/cmdline").read_bytes():
                    break
                time.sleep(0.1)
            else:
                raise SystemExit("API did not stop; PID retained")
        pid_file.unlink(missing_ok=True)
        running = False
        print(f"IRI API stopped ({args.namespace})")
        if args.action == "down":
            return
    if not running:
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError as error:
                raise SystemExit(f"API port {port} unavailable for namespace {args.namespace}: {error}")
        if stale:
            subprocess.run([os.environ.get("MAVEN", str(app / "mvnw")),
                            "-s", str(settings), "-B", "-DskipTests", "package"], cwd=app, check=True)
        env = dict(os.environ, API_PORT=str(port), DB_URL=f"jdbc:oracle:thin:@localhost:{51521 + offset}/FREEPDB1")
        with log_file.open("ab") as log:
            process = subprocess.Popen(["java", "-jar", str(jar)], env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        pid = process.pid
        pid_file.write_text(str(pid))
    for _ in range(90):
        try:
            with urllib.request.urlopen(url + "/health", timeout=3) as response:
                if json.load(response) == {"STATUS": "UP", "DB": "UP"}:
                    print(f"IRI API ready: {url} (PID {pid}, log {log_file})")
                    return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise SystemExit(f"API did not become healthy; inspect {log_file}")


if __name__ == "__main__":
    main()
