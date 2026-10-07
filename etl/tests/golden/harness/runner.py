"""Runs one legacy script in the pinned legacy container, exactly like run.sh.

Mounts (all read-only): etl/run.sh -> /opt/etl/run.sh, etl/scripts ->
/opt/etl/scripts, the generated config.ini -> /opt/etl/config.ini and
legacy/sitecustomize.py -> /opt/etl/sitecustomize.py. The command is
`/opt/etl/run.sh <script>.py`, the same line the crontab uses; run.sh's
PYTHONPATH=/opt/etl is what makes the interpreter pick up the shim.
"""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import settings

IMAGE_INPUTS = (
    settings.LEGACY_DIR / "Dockerfile",
    settings.LEGACY_DIR / "constraints.txt",
    settings.LEGACY_DIR / "requirements-shim.txt",
    settings.ETL_DIR / "requirements.txt",
)


@dataclass
class RunResult:
    exit_code: int
    output: str


def image_tag() -> str:
    digest = hashlib.sha256(settings.LEGACY_BASE_IMAGE.encode())
    for path in IMAGE_INPUTS:
        digest.update(path.read_bytes())
    return "%s:%s" % (settings.LEGACY_IMAGE_REPO, digest.hexdigest()[:12])


def ensure_image() -> str:
    tag = image_tag()
    present = (
        subprocess.run(
            ["docker", "image", "inspect", tag], capture_output=True
        ).returncode
        == 0
    )
    if not present:
        subprocess.run(
            [
                "docker",
                "build",
                "--build-arg",
                "BASE_IMAGE=%s" % settings.LEGACY_BASE_IMAGE,
                "-f",
                str(settings.LEGACY_DIR / "Dockerfile"),
                "-t",
                tag,
                str(settings.ETL_DIR),
            ],
            check=True,
        )
    return tag


def legacy_mounts(config_path: Path) -> list[tuple[Path, str]]:
    """(host source, container target) pairs, all mounted read-only."""
    return [
        (settings.ETL_DIR / "run.sh", "/opt/etl/run.sh"),
        (settings.ETL_DIR / "scripts", "/opt/etl/scripts"),
        (config_path, "/opt/etl/config.ini"),
        (settings.LEGACY_DIR / "sitecustomize.py", "/opt/etl/sitecustomize.py"),
    ]


def legacy_environment(frozen_time: str) -> dict[str, str]:
    return {
        "TZ": "UTC",
        "GOLDEN_AWS_ENDPOINT_URL": settings.LOCALSTACK_URL,
        "GOLDEN_FROZEN_TIME": frozen_time,
    }


def legacy_command(script: str) -> list[str]:
    return ["/opt/etl/run.sh", "%s.py" % script]


def docker_command(
    image: str,
    script: str,
    frozen_time: str,
    config_path: Path,
    name: str = "otterworks-etl-golden",
) -> list[str]:
    env = [
        arg
        for key, value in legacy_environment(frozen_time).items()
        for arg in ("-e", "%s=%s" % (key, value))
    ]
    mounts = [
        arg
        for src, dst in legacy_mounts(config_path)
        for arg in ("--mount", "type=bind,source=%s,target=%s,readonly" % (src, dst))
    ]
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        settings.DOCKER_NETWORK,
        *env,
        *mounts,
        image,
        *legacy_command(script),
    ]


def run(image: str, script: str, frozen_time: str, config_path: Path) -> RunResult:
    name = "otterworks-etl-golden-%s" % uuid.uuid4().hex[:12]
    try:
        proc = subprocess.run(
            docker_command(image, script, frozen_time, config_path, name),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=settings.CONTAINER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # Killing the docker client does not stop the container; remove it
        # so a stuck script cannot keep writing to the local stack.
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        raise
    return RunResult(exit_code=proc.returncode, output=proc.stdout)
