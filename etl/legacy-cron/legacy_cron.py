"""Entrypoint of the legacy-etl-cron container (docker-compose.airflow.yml).

Runs the committed etl/crontab, mounted read-only and unmodified, with
supercronic, so every line still executes exactly as written:
``/opt/etl/run.sh <script>.py >> /var/log/etl/<name>.log 2>&1``. Each
/var/log/etl target named in the crontab is a symlink to /dev/stdout, so the
"log files" land in the container log (supercronic tags each line with the job).
Only the lines present in the crontab are scheduled: removing a line and
recreating the container is the cutover, restoring it is the rollback.

/opt/etl/config.ini is a symlink to a file rendered at start by the golden
harness renderer (etl/tests/golden/harness/config_ini.py): local endpoints and
dev credentials only. The committed etl/config.ini is never read.

  legacy_cron.py serve              render config, link logs, exec supercronic
  legacy_cron.py run <script>.py    run that script's crontab line now (exit 3 if absent)
  legacy_cron.py healthcheck        exit 0 when supercronic's metrics endpoint answers

Runs on the legacy Python 3.9 runtime, so it sticks to 3.9 syntax.
"""

from __future__ import annotations

import http.client
import os
import re
import subprocess
import sys
import tempfile
from typing import List, NamedTuple, Optional

CRONTAB = "/opt/etl/crontab"
CONFIG_PATH = "/run/legacy-etl/config.ini"
HARNESS_DIR = "/opt/legacy-cron/golden"
LOG_DIR = "/var/log/etl"
SUPERCRONIC = "/usr/local/bin/supercronic"
METRICS_ADDRESS = "127.0.0.1:9746"
NOT_SCHEDULED_EXIT_CODE = 3

_ENV_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")
_REDIRECT = re.compile(r"(?:^|\s)\d?>>?\s*(?P<path>[^\s;&|]+)")
_SCRIPT = re.compile(r"\brun\.sh\s+(?P<script>[A-Za-z0-9_.-]+\.py)\b")


class Job(NamedTuple):
    schedule: str
    command: str


def parse_crontab(text: str) -> List[Job]:
    jobs = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or _ENV_LINE.match(line):
            continue
        if line.startswith("@"):
            schedule, _, command = line.partition(" ")
        else:
            fields = line.split(None, 5)
            if len(fields) < 6:
                raise ValueError("malformed crontab line: %r" % raw)
            schedule, command = " ".join(fields[:5]), fields[5]
        jobs.append(Job(schedule, command.strip()))
    return jobs


def log_targets(jobs: List[Job], log_dir: str = LOG_DIR) -> List[str]:
    prefix = log_dir.rstrip("/") + "/"
    targets = []
    for job in jobs:
        for match in _REDIRECT.finditer(job.command):
            path = match.group("path")
            if path.startswith(prefix) and path not in targets:
                targets.append(path)
    return targets


def link_logs_to_stdout(targets: List[str]) -> None:
    for path in targets:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.lexists(path):
            os.remove(path)
        os.symlink("/dev/stdout", path)


def job_for_script(jobs: List[Job], script: str) -> Optional[Job]:
    for job in jobs:
        match = _SCRIPT.search(job.command)
        if match and match.group("script") == script:
            return job
    return None


def render_config(
    path: str = CONFIG_PATH, harness_dir: str = HARNESS_DIR, env=os.environ
) -> None:
    if harness_dir not in sys.path:
        sys.path.insert(0, harness_dir)
    from harness import config_ini

    text = config_ini.render(
        services_url="",
        overrides={
            "services": {
                "document_service_url": env["LEGACY_CRON_DOCUMENT_SERVICE_URL"],
                "file_service_url": env["LEGACY_CRON_FILE_SERVICE_URL"],
            }
        },
    )
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".config.ini.")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.remove(tmp)
        raise


def prepare() -> List[Job]:
    with open(CRONTAB) as fh:
        jobs = parse_crontab(fh.read())
    render_config()
    link_logs_to_stdout(log_targets(jobs))
    return jobs


def serve() -> None:
    jobs = prepare()
    print(
        "[legacy-etl-cron] %d job(s) scheduled from %s" % (len(jobs), CRONTAB),
        flush=True,
    )
    for job in jobs:
        print("[legacy-etl-cron]   %s  %s" % (job.schedule, job.command), flush=True)
    os.execv(
        SUPERCRONIC,
        [SUPERCRONIC, "-prometheus-listen-address", METRICS_ADDRESS, CRONTAB],
    )


def run(script: str) -> int:
    job = job_for_script(prepare(), script)
    if job is None:
        sys.stderr.write(
            "[legacy-etl-cron] %s has no line in %s (cut over to Airflow?)\n"
            % (script, CRONTAB)
        )
        return NOT_SCHEDULED_EXIT_CODE
    print("[legacy-etl-cron] running now: %s" % job.command, flush=True)
    return subprocess.call(["/bin/sh", "-c", job.command])


def healthcheck() -> int:
    try:
        host, port = METRICS_ADDRESS.rsplit(":", 1)
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        try:
            conn.request("GET", "/metrics")
            return 0 if conn.getresponse().status == 200 else 1
        finally:
            conn.close()
    except OSError:
        return 1


def main(argv: List[str]) -> int:
    command = argv[0] if argv else "serve"
    if command == "serve":
        serve()
        return 0
    if command == "run" and len(argv) == 2:
        return run(argv[1])
    if command == "healthcheck":
        return healthcheck()
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
