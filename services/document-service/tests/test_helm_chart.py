"""The chart renders the folder-digest and database values as explicit env."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

CHART = Path(__file__).resolve().parents[3] / "infrastructure" / "helm" / "document-service"
HELM = shutil.which("helm")

pytestmark = pytest.mark.skipif(HELM is None or not CHART.is_dir(), reason="helm not installed")


def _env(*sets: str) -> dict[str, dict]:
    assert HELM
    args = [HELM, "template", "doc", str(CHART), "--show-only", "templates/deployment.yaml"]
    args += ["--set", "image.tag=test"]
    for value in sets:
        args += ["--set", value]
    rendered = yaml.safe_load(subprocess.run(args, check=True, capture_output=True).stdout)
    container = rendered["spec"]["template"]["spec"]["containers"][0]
    return {item["name"]: item for item in container["env"]}


def test_defaults_keep_the_worker_off() -> None:
    env = _env()
    assert env["DOC_SVC_FOLDER_DIGEST_ENABLED"]["value"] == "false"
    assert env["DOC_SVC_FOLDER_DIGEST_INTERVAL_SECONDS"]["value"] == "15"
    assert env["DOC_SVC_FOLDER_DIGEST_CONCURRENCY"]["value"] == "4"
    for name in (
        "DOC_SVC_DB_STATEMENT_TIMEOUT_MS",
        "DOC_SVC_DB_POOL_SIZE",
        "DOC_SVC_DB_MAX_OVERFLOW",
        "DOC_SVC_DATABASE_URL",
    ):
        assert name not in env


def test_values_render_as_env() -> None:
    env = _env(
        "folderDigest.enabled=true",
        "folderDigest.intervalSeconds=5",
        "folderDigest.concurrency=8",
        "database.statementTimeoutMs=3000",
        "database.poolSize=5",
        "database.maxOverflow=0",
        "database.urlSecret.name=oncall-postgres",
        "database.urlSecret.key=url",
    )
    assert env["DOC_SVC_FOLDER_DIGEST_ENABLED"]["value"] == "true"
    assert env["DOC_SVC_FOLDER_DIGEST_INTERVAL_SECONDS"]["value"] == "5"
    assert env["DOC_SVC_FOLDER_DIGEST_CONCURRENCY"]["value"] == "8"
    assert env["DOC_SVC_DB_STATEMENT_TIMEOUT_MS"]["value"] == "3000"
    assert env["DOC_SVC_DB_POOL_SIZE"]["value"] == "5"
    assert env["DOC_SVC_DB_MAX_OVERFLOW"]["value"] == "0"
    assert env["DOC_SVC_DATABASE_URL"]["valueFrom"] == {
        "secretKeyRef": {"name": "oncall-postgres", "key": "url"}
    }
