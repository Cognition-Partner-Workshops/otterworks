"""Runs `airflow dags test` in a throwaway container of the Airflow image.

The container uses the image the Compose stack runs (otterworks/etl-airflow:local, Airflow
2.8 / Python 3.11 with the provider hooks), with its own SQLite metadata DB so parity runs
never touch the stack's scheduler state. It joins the harness's Docker network, so its
Connections point at the same LocalStack, Postgres (otterworks_etl_golden) and MeiliSearch
the harness seeds and snapshots. Variables come from etl/airflow/.env.example (the committed
defaults) plus a scenario's overrides, as AIRFLOW_VAR_* on each `docker exec`.

The repo is mounted read-only at its host path and the Docker socket is mounted, so a toy
DAG can start the pinned legacy container with the same bind mounts the harness uses.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from . import runner, settings

AIRFLOW_IMAGE = os.environ.get("GOLDEN_AIRFLOW_IMAGE", "otterworks/etl-airflow:local")
ENV_EXAMPLE = settings.ETL_DIR / "airflow" / ".env.example"
PARITY_DIR = settings.GOLDEN_DIR / "parity"
TOY_DAG_FOLDER = PARITY_DIR / "dags"
REQUIREMENTS = PARITY_DIR / "requirements-airflow.txt"
DOCKER_SOCKET = Path(os.environ.get("GOLDEN_DOCKER_SOCKET", "/var/run/docker.sock"))
DAG_STATES = ("success", "failed")
# `airflow dags state` needs the DAG in the serialized `dag` table, which `dags test` skips.
DAG_RUN_STATE = """
import sys
from airflow.models import DagRun
from airflow.utils import timezone
runs = DagRun.find(dag_id=sys.argv[1], execution_date=timezone.parse(sys.argv[2]))
print(runs[0].state if runs else "no-dagrun")
"""


class AirflowError(RuntimeError):
    pass


def default_variables(path: Path = ENV_EXAMPLE) -> dict[str, str]:
    """Committed Variable defaults: {key: raw env value}."""
    out = {}
    for line in path.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and name.startswith("AIRFLOW_VAR_"):
            out[name[len("AIRFLOW_VAR_") :].lower()] = value
    return out


def connection_ids(path: Path = ENV_EXAMPLE) -> set[str]:
    return {
        line.split("=", 1)[0][len("AIRFLOW_CONN_") :].lower()
        for line in path.read_text().splitlines()
        if line.startswith("AIRFLOW_CONN_")
    }


def _http(url: str, **extra) -> dict:
    scheme, _, rest = url.partition("://")
    host, _, port = rest.split("/", 1)[0].partition(":")
    conn = {"conn_type": "http", "host": host, "schema": scheme, **extra}
    if port:
        conn["port"] = int(port)
    return conn


def connections(services_url: str) -> dict[str, dict]:
    """Every Connection in .env.example, pointed at the harness's local endpoints."""
    return {
        "aws_default": {
            "conn_type": "aws",
            "login": settings.AWS_ACCESS_KEY,
            "password": settings.AWS_SECRET_KEY,
            "extra": {
                "region_name": settings.AWS_REGION,
                "endpoint_url": settings.LOCALSTACK_URL,
            },
        },
        "otterworks_postgres": {
            "conn_type": "postgres",
            "host": settings.PG_HOST,
            "port": settings.PG_PORT,
            "schema": settings.PG_DB,
            "login": settings.PG_USER,
            "password": settings.PG_PASSWORD,
        },
        "otterworks_meilisearch": _http(settings.MEILI_URL, password=settings.MEILI_API_KEY),
        "otterworks_document_service": _http("%s/document-service" % services_url),
        "otterworks_file_service": _http("%s/file-service" % services_url),
    }


def variable_value(value) -> str:
    """Airflow env Variables are strings; booleans and numbers as JSON literals."""
    return value if isinstance(value, str) else json.dumps(value)


def run_environment(
    services_url: str, overrides: dict, config_path: Path, frozen_time: str, legacy_image: str
) -> dict[str, str]:
    defaults = default_variables()
    unknown = set(overrides) - set(defaults)
    if unknown:
        raise AirflowError(
            "Variable override(s) %s are not defined in %s" % (sorted(unknown), ENV_EXAMPLE)
        )
    env = {
        "AIRFLOW_VAR_%s" % k.upper(): v
        for k, v in {**defaults, **{k: variable_value(v) for k, v in overrides.items()}}.items()
    }
    env.update(
        ("AIRFLOW_CONN_%s" % k.upper(), json.dumps(v)) for k, v in connections(services_url).items()
    )
    env.update(
        PARITY_CONFIG_PATH=str(config_path),
        PARITY_FROZEN_TIME=frozen_time,
        PARITY_LEGACY_IMAGE=legacy_image,
    )
    return env


def ensure_image(image: str = AIRFLOW_IMAGE) -> str:
    if subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode:
        raise AirflowError(
            "Airflow image %s not found; build it with "
            "`docker build -t %s etl/airflow` (make etl-parity does)" % (image, image)
        )
    return image


class AirflowContainer:
    def __init__(self, image: str = AIRFLOW_IMAGE, log_path: Path | None = None):
        self.image = image
        self.name = "otterworks-etl-parity-airflow-%s" % uuid.uuid4().hex[:12]
        self.log_path = log_path
        self.version = ""

    def _log(self, text: str) -> None:
        if self.log_path:
            with self.log_path.open("a") as f:
                f.write(text)

    def start(self) -> None:
        cmd = [
            "docker", "run", "-d", "--rm", "--name", self.name,
            "--network", settings.DOCKER_NETWORK,
            "--group-add", str(DOCKER_SOCKET.stat().st_gid),
            "-v", "%s:%s:ro" % (settings.REPO_ROOT, settings.REPO_ROOT),
            "-v", "%s:/var/run/docker.sock" % DOCKER_SOCKET,
            "-e", "AIRFLOW__CORE__LOAD_EXAMPLES=false",
            "-e", "AIRFLOW__CORE__EXECUTOR=SequentialExecutor",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            *[
                arg
                for key in ("GOLDEN_DOCKER_NETWORK", "GOLDEN_LOCALSTACK_URL", "GOLDEN_CONTAINER_TIMEOUT")
                if key in os.environ
                for arg in ("-e", "%s=%s" % (key, os.environ[key]))
            ],
            "--entrypoint", "bash", self.image, "-c", "sleep infinity",
        ]  # fmt: skip
        subprocess.run(cmd, check=True, capture_output=True)
        setup = (
            'set -euo pipefail; af="$(python -c "import airflow; print(airflow.__version__)")"; '
            'py="$(python -c "import sys; print(f\\"{sys.version_info[0]}.{sys.version_info[1]}\\")")"; '
            "pip install --quiet --no-cache-dir --constraint "
            '"https://raw.githubusercontent.com/apache/airflow/constraints-${af}/constraints-${py}.txt" '
            "-r %s; airflow db migrate; airflow version" % REQUIREMENTS
        )
        proc = self.exec(["bash", "-c", setup], {})
        if proc.returncode:
            raise AirflowError("parity Airflow container setup failed:\n%s" % proc.stdout[-4000:])
        self.version = "Airflow %s" % proc.stdout.strip().splitlines()[-1].strip()

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    def __enter__(self) -> AirflowContainer:
        try:
            self.start()
        except BaseException:
            self.stop()
            raise
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def exec(self, argv: list[str], env: dict[str, str], timeout: float | None = None):
        cmd = ["docker", "exec"]
        for key, value in env.items():
            cmd += ["-e", "%s=%s" % (key, value)]
        proc = subprocess.run(
            [*cmd, self.name, *argv],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        self._log("$ %s\n%s\n" % (" ".join(argv), proc.stdout))
        return proc

    def dags_test(
        self, dag_id: str, run_date: str, env: dict[str, str], subdir: Path | None
    ) -> runner.RunResult:
        """`airflow dags test`; exit_code is 0 for a successful DagRun, 1 for a failed one."""
        where = ["--subdir", str(subdir)] if subdir else []
        conf = json.dumps({"run_date": run_date[:10]})
        proc = self.exec(
            ["airflow", "dags", "test", *where, "--conf", conf, dag_id, run_date],
            env,
            timeout=settings.CONTAINER_TIMEOUT_SECONDS,
        )
        state = self.exec(["python", "-c", DAG_RUN_STATE, dag_id, run_date], env)
        last = (state.stdout.strip().splitlines() or [""])[-1].strip()
        if state.returncode or last not in DAG_STATES:
            raise AirflowError(
                "%s: no finished DagRun for %s (dags test exit %d, state %r):\n%s"
                % (dag_id, run_date, proc.returncode, last, proc.stdout[-4000:])
            )
        if (last == "success") != (proc.returncode == 0):
            raise AirflowError(
                "%s: dags test exit %d disagrees with DagRun state %s" % (dag_id, proc.returncode, last)
            )
        return runner.RunResult(exit_code=0 if last == "success" else 1, output=proc.stdout)

    def resolved_variables(self, keys: list[str], env: dict[str, str]) -> dict[str, str]:
        out = {}
        for key in keys:
            proc = self.exec(["airflow", "variables", "get", key], env)
            out[key] = (proc.stdout.strip().splitlines() or [""])[-1] if not proc.returncode else "<error>"
        return out
